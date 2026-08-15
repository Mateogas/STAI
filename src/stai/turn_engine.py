"""One deep turn-processing module for all AISHA policy conversations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from stai.guardrails import REFUSALS, redact_pii, validate_response_relevance
from stai.handbook import ACTIVE_HANDBOOK_VERSION
from stai.models import (
    Abstention,
    AgentResponseDraft,
    AgentTurnDecision,
    ApplicabilityStatus,
    ClarificationRequest,
    DialogueAct,
    EscalationConfirmation,
    EscalationEligibility,
    EscalationOffer,
    EvidenceState,
    ExecutionMode,
    GroundedPolicyAnswer,
    OnboardingTopic,
    PolicyCitation,
    ResolvedTurn,
)
from stai.policy import evaluate_applicability, validate_claim_support
from stai.retriever import HandbookIndex, HandbookPageRecord, InMemoryHandbookIndex
from stai.state import Repo


AgentRunner = Callable[[object, list[dict], dict], object]


def _topic_for_policy_id(policy_id: str) -> OnboardingTopic:
    if policy_id.startswith("PAY-"):
        return OnboardingTopic.PAYROLL
    if policy_id.startswith("ACC-"):
        return OnboardingTopic.RESOURCE_ACCESS
    return OnboardingTopic.HR_POLICIES


class PolicyTurnEngine:
    """Run ReAct first, then validate and execute one bounded conversation turn."""

    def __init__(
        self,
        repo: Repo,
        records: list[HandbookPageRecord],
        *,
        index: HandbookIndex | None = None,
        agent_runner: AgentRunner | None = None,
        input_classifier=None,
        case_workflow=None,
        clarification_workflow=None,
        history_limit: int = 8,
        **_legacy_options,
    ) -> None:
        self.repo = repo
        self.records = records
        self.index = index or InMemoryHandbookIndex(records)
        self.agent_runner = agent_runner
        self.input_classifier = input_classifier
        if case_workflow is None:
            from stai.cases import CaseWorkflow

            case_workflow = CaseWorkflow(repo)
        if clarification_workflow is None:
            from stai.clarifications import PolicyClarificationWorkflow

            clarification_workflow = PolicyClarificationWorkflow(repo)
        self.case_workflow = case_workflow
        self.clarification_workflow = clarification_workflow
        self.history_limit = history_limit
        self.version = records[0].handbook_version if records else ACTIVE_HANDBOOK_VERSION

    def handle_turn(self, conversation_id: str, message: str):
        """The sole policy-turn interface used by transport callers and tests."""
        conversation = self.repo.get_policy_conversation(conversation_id)
        if not conversation:
            raise KeyError("conversation not found")
        self.repo.validate_policy_message(message)
        history = self.repo.list_policy_messages(conversation_id)[-self.history_limit :]
        previous_context = self._latest_context(conversation_id, history)
        pending_offer = self.repo.get_pending_escalation_offer_for_conversation(
            conversation_id
        )
        blocked_category = self._blocked_category(message)
        user_message = self.repo.add_policy_message(conversation_id, "hire", message)
        profile = self.repo.get_hire_profile(conversation["hire_id"])

        if blocked_category:
            plan = ResolvedTurn(
                dialogue_act=DialogueAct.UNSUPPORTED,
                standalone_query=message,
            )
            response = Abstention(
                text=REFUSALS[blocked_category],
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.INSUFFICIENT,
                reason="unsupported_topic",
            )
            mode = ExecutionMode.DETERMINISTIC
        else:
            if self.agent_runner is None:
                from stai.agent import AgentUnavailableError

                raise AgentUnavailableError(
                    "no ReAct runner is configured",
                    stage="runner_configuration",
                )
            runtime_context = self._runtime_context(
                conversation,
                profile,
                previous_context,
                pending_offer,
            )
            run = self.agent_runner(
                profile,
                [*history, {"role": "hire", "text": message}],
                runtime_context,
            )
            decision, capture = self._unpack_run(run)
            plan = decision.plan
            self._validate_plan(plan)
            response = self._execute_decision(
                conversation_id,
                user_message["id"],
                decision,
                capture,
                pending_offer,
                conversation,
            )
            mode = ExecutionMode.AGENT

        response = self._redact(response)
        self.repo.save_policy_response(
            conversation_id,
            response,
            dialogue_act=plan.dialogue_act.value,
            resolved_topic=plan.topic.value if plan.topic else None,
            referenced_message_id=plan.referenced_message_id,
            execution_mode=mode.value,
        )
        return response

    @staticmethod
    def _unpack_run(run):
        if hasattr(run, "decision") and hasattr(run, "capture"):
            return AgentTurnDecision.model_validate(run.decision), run.capture
        if isinstance(run, tuple) and len(run) == 2:
            return AgentTurnDecision.model_validate(run[0]), run[1]
        raise TypeError("agent runner must return a typed decision and run capture")

    def _execute_decision(
        self,
        conversation_id: str,
        user_message_id: str,
        decision: AgentTurnDecision,
        capture,
        pending_offer: dict | None,
        conversation: dict,
    ):
        draft = decision.response
        if draft.handbook_version != self.version:
            raise ValueError("agent response used a non-active handbook version")

        if draft.response_type == "case_action":
            if draft.case_action == "consent_pending_offer":
                if decision.plan.dialogue_act != DialogueAct.CONSENT:
                    raise ValueError("case consent requires a consent plan")
                return self._consent_offer(
                    conversation_id, pending_offer, conversation["hire_id"], decision.plan
                )
            if decision.plan.dialogue_act != DialogueAct.ACTION_STATUS:
                raise ValueError("case status requires an action-status plan")
            return self._case_status(conversation_id, pending_offer)

        if draft.response_type == "grounded_answer":
            if decision.plan.dialogue_act not in {
                DialogueAct.QUESTION,
                DialogueAct.FOLLOW_UP,
                DialogueAct.CLARIFICATION,
                DialogueAct.CAPABILITY_DISCOVERY,
            }:
                raise ValueError("grounded response does not match the planned dialogue act")
            return self._grounded_response(draft, decision.plan, capture)
        if draft.response_type == "clarification_request":
            return ClarificationRequest(
                text=draft.text,
                handbook_version=draft.handbook_version,
                applicability=draft.applicability,
                evidence_state=draft.evidence_state,
                citations=draft.citations,
                question=draft.question or draft.text,
                choices=draft.choices,
            )
        if draft.response_type == "abstention":
            return Abstention(
                text=draft.text,
                handbook_version=draft.handbook_version,
                applicability=draft.applicability,
                evidence_state=draft.evidence_state,
                citations=draft.citations,
                reason=draft.reason or "insufficient_evidence",
            )
        return self._prepare_escalation_offer(
            conversation_id,
            user_message_id,
            decision.plan,
            draft,
            capture,
            conversation,
        )

    def _grounded_response(
        self, draft: AgentResponseDraft, plan: ResolvedTurn, capture
    ) -> GroundedPolicyAnswer:
        response = GroundedPolicyAnswer(
            text=draft.text,
            handbook_version=draft.handbook_version,
            applicability=draft.applicability,
            evidence_state=draft.evidence_state,
            citations=draft.citations,
            claims=draft.claims,
        )
        identities = set(getattr(capture, "retrieved_identities", set()))
        validate_claim_support(response, identities)
        self._validate_exact_claims(response, capture)
        self._validate_applicability(response, capture)
        validate_response_relevance(
            response,
            plan.topic.value if plan.topic else None,
            self.records,
        )
        return response

    def _prepare_escalation_offer(
        self,
        conversation_id: str,
        user_message_id: str,
        plan: ResolvedTurn,
        draft: AgentResponseDraft,
        capture,
        conversation: dict,
    ):
        if not plan.topic:
            raise ValueError("an escalation offer requires a resolved topic")
        self._validate_citation_identities(draft.citations, capture)
        self._validate_exact_excerpt(
            draft.safe_known_text or "", draft.citations, capture
        )
        if draft.evidence_state not in {
            EvidenceState.INSUFFICIENT,
            EvidenceState.POLICY_CONFLICT,
        }:
            raise ValueError("an escalation offer requires a material evidence gap")
        gap = EscalationEligibility(
            eligible=True,
            reason=draft.eligibility_reason or "material handbook gap",
            gap_kind=draft.gap_kind,
            safe_known_text=draft.safe_known_text,
            unresolved_question=draft.unresolved_question,
            policy_ids=list(dict.fromkeys(c.policy_id for c in draft.citations)),
        )
        approved = self.clarification_workflow.find_approved(
            plan.standalone_query,
            policy_ids=set(gap.policy_ids),
            topic=plan.topic.value,
            hire_id=conversation["hire_id"],
            as_of=date.fromisoformat(conversation["simulated_date"]),
        )
        if approved:
            citation = draft.citations[0]
            base = GroundedPolicyAnswer(
                text=f"{gap.safe_known_text} {citation.render()}",
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.READY,
                citations=[citation],
                claims=[
                    {
                        "text": gap.safe_known_text,
                        "citation_indexes": [0],
                    }
                ],
            )
            return self.clarification_workflow.supplement(base, approved)
        return self._offer_evidence_gap(
            conversation_id,
            user_message_id,
            plan,
            draft.citations[0],
            gap,
        )

    def _validate_plan(self, plan: ResolvedTurn) -> None:
        if plan.dialogue_act in {DialogueAct.QUESTION, DialogueAct.FOLLOW_UP} and not plan.topic:
            raise ValueError("policy questions require one resolved onboarding topic")
        for policy_id in plan.policy_ids:
            topic = _topic_for_policy_id(policy_id)
            if plan.topic and topic != plan.topic:
                raise ValueError("agent plan mixed policy IDs from another topic")
        if plan.catalog_scope and plan.dialogue_act != DialogueAct.CAPABILITY_DISCOVERY:
            raise ValueError("catalog scope is valid only for policy discovery")

    def _validate_applicability(self, response: GroundedPolicyAnswer, capture) -> None:
        statuses = []
        for citation in response.citations:
            record = next(
                (
                    row
                    for row in self.records
                    if row.policy_id == citation.policy_id
                    and row.handbook_version == citation.handbook_version
                    and row.page == citation.page_start
                ),
                None,
            )
            if not record:
                raise ValueError("citation is not an active verified handbook page")
            statuses.append(evaluate_applicability(record, self._profile_from_capture(capture)))
        if statuses and all(
            item.status == ApplicabilityStatus.DOES_NOT_APPLY for item in statuses
        ) and response.applicability != ApplicabilityStatus.DOES_NOT_APPLY:
            raise ValueError("general policy existence was conflated with Hire applicability")

    @staticmethod
    def _profile_from_capture(capture):
        profile = getattr(capture, "profile", None)
        if profile is None:
            raise ValueError("agent run did not retain the confirmed Hire Profile")
        return profile

    def _validate_exact_claims(self, response: GroundedPolicyAnswer, capture) -> None:
        for claim in response.claims:
            citations = [response.citations[index] for index in claim.citation_indexes]
            self._validate_exact_excerpt(claim.text, citations, capture)

    def _validate_citation_identities(self, citations, capture) -> None:
        identities = set(getattr(capture, "retrieved_identities", set()))
        for citation in citations:
            pages = range(citation.page_start, (citation.page_end or citation.page_start) + 1)
            if not all(
                (citation.policy_id, citation.handbook_version, page) in identities
                for page in pages
            ):
                raise ValueError("citation does not match evidence retrieved in this run")

    def _validate_exact_excerpt(self, excerpt: str, citations, capture) -> None:
        self._validate_citation_identities(citations, capture)
        needle = self._normalized(excerpt)
        contents = getattr(capture, "evidence_contents", {})
        for citation in citations:
            pages = range(citation.page_start, (citation.page_end or citation.page_start) + 1)
            for page in pages:
                identity = (citation.policy_id, citation.handbook_version, page)
                if needle and needle in self._normalized(contents.get(identity, "")):
                    return
        raise ValueError("claim support is not an exact excerpt from cited evidence")

    @staticmethod
    def _normalized(value: str) -> str:
        return " ".join(value.casefold().split())

    def _consent_offer(
        self,
        conversation_id: str,
        pending_offer: dict | None,
        hire_id: str,
        plan: ResolvedTurn,
    ) -> EscalationConfirmation:
        if not pending_offer:
            raise ValueError("consent cannot mutate state without a pending offer")
        from stai.cases import CaseActor

        case = self.case_workflow.consent_offer(
            conversation_id,
            pending_offer["offer_id"],
            expected_version=pending_offer["resource_version"],
            actor=CaseActor.hire(hire_id),
        )
        return EscalationConfirmation(
            text=(
                f"Case {case['case_id']} was created successfully and is open. "
                f"It was routed to {case['route_owner']} through {case['route_channel']}."
            ),
            handbook_version=self.version,
            applicability=ApplicabilityStatus.APPLIES,
            evidence_state=EvidenceState.READY,
            case_id=case["case_id"],
            route_owner=case["route_owner"],
            route_channel=case["route_channel"],
            topic=plan.topic or OnboardingTopic(pending_offer["topic"]),
            version=case["resource_version"],
        )

    def _case_status(self, conversation_id: str, pending_offer: dict | None):
        latest = self.repo.get_latest_escalation_confirmation(conversation_id)
        if latest:
            case = self.repo.get_escalation_case(latest["case_id"])
            if case:
                return EscalationConfirmation(
                    text=(
                        f"Yes—case {case['case_id']} was created successfully and is "
                        f"{case['status']}. It was routed to {case['route_owner']} "
                        f"through {case['route_channel']}."
                    ),
                    handbook_version=self.version,
                    applicability=ApplicabilityStatus.APPLIES,
                    evidence_state=EvidenceState.READY,
                    case_id=case["case_id"],
                    route_owner=case["route_owner"],
                    route_channel=case["route_channel"],
                    topic=OnboardingTopic(case["topic"]),
                    version=case["resource_version"],
                )
        if pending_offer:
            payload = self.repo.get_escalation_offer(pending_offer["offer_id"])
            if payload:
                return EscalationOffer.model_validate(payload).model_copy(
                    update={
                        "text": (
                            "Not yet—nothing has been shared. Review the summary and select "
                            "Consent and create case if you want me to create it."
                        )
                    }
                )
        return ClarificationRequest(
            text=(
                "I can't find a case created in this conversation. Which onboarding "
                "area needs human support?"
            ),
            handbook_version=self.version,
            applicability=ApplicabilityStatus.APPLIES,
            evidence_state=EvidenceState.INSUFFICIENT,
            question="Which onboarding area needs human support?",
            choices=["Payroll", "Resource Access", "HR Policies"],
        )

    def _offer_evidence_gap(
        self,
        conversation_id: str,
        user_message_id: str,
        plan: ResolvedTurn,
        citation: PolicyCitation,
        gap: EscalationEligibility,
    ):
        pending = self.repo.get_pending_escalation_offer_for_conversation(conversation_id)
        if pending:
            return self._pending_offer_response(pending)
        from stai.cases import CaseActor

        topic = plan.topic or OnboardingTopic.HR_POLICIES
        existing = next(
            (
                case
                for case in self.case_workflow.list_cases(
                    CaseActor.hire(), parent_conversation_id=conversation_id
                )
                if case["status"] == "open" and case["topic"] == topic.value
            ),
            None,
        )
        if existing:
            return EscalationConfirmation(
                text=f"An open HR clarification ticket already covers this conversation: case {existing['case_id']}.",
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.READY,
                case_id=existing["case_id"],
                route_owner=existing["route_owner"],
                route_channel=existing["route_channel"],
                topic=OnboardingTopic(existing["topic"]),
                version=existing["resource_version"],
            )
        record = next(
            (row for row in self.records if row.policy_id in gap.policy_ids and row.route),
            None,
        )
        owner = (
            record.route if record and record.route else f"{topic.value}_support"
        ).replace("_", " ").title()
        question = gap.unresolved_question or plan.standalone_query
        summary = f"Clarify {gap.gap_kind.value.replace('_', ' ')}: {question}"[:500]
        row = self.repo.create_escalation_offer(
            conversation_id,
            user_message_id,
            topic.value,
            owner,
            "Fictional HR Help Desk",
            summary,
            gap.policy_ids,
        )
        self.clarification_workflow.record_offer_gap(row["offer_id"], gap)
        return EscalationOffer(
            text=(
                f"The handbook confirms: {gap.safe_known_text} {citation.render()}\n\n"
                f"However, {gap.reason}. Further clarification from HR is needed. "
                "Would you like me to create an HR clarification ticket?"
            ),
            handbook_version=self.version,
            applicability=ApplicabilityStatus.APPLIES,
            evidence_state=EvidenceState.INSUFFICIENT,
            citations=[citation],
            offer_id=row["offer_id"],
            route_owner=owner,
            route_channel="Fictional HR Help Desk",
            proposed_summary=summary,
            topic=topic,
            version=row["version"],
            gap_kind=gap.gap_kind,
            safe_known_text=gap.safe_known_text,
            unresolved_question=gap.unresolved_question,
            eligibility_reason=gap.reason,
        )

    def _pending_offer_response(self, pending: dict) -> EscalationOffer:
        payload = self.repo.get_escalation_offer(pending["offer_id"])
        if payload and not payload.get("citations") and pending.get("policy_ids"):
            record = next(
                (
                    row
                    for row in self.records
                    if row.policy_id in pending["policy_ids"]
                    and row.content == payload.get("safe_known_text")
                ),
                None,
            )
            if record:
                payload["citations"] = [
                    {
                        "policy_id": record.policy_id,
                        "handbook_version": record.handbook_version,
                        "page_start": record.page,
                    }
                ]
        return EscalationOffer.model_validate(payload)

    def _blocked_category(self, message: str) -> str | None:
        lowered = message.lower()
        injection_markers = (
            "ignore all previous",
            "ignore previous instructions",
            "reveal your system",
            "show your system prompt",
            "you are now dan",
            "override your rules",
            "ignore the handbook",
        )
        if any(marker in lowered for marker in injection_markers):
            return "injection"
        if not self.input_classifier:
            return None
        verdict = self.input_classifier(message)
        return None if verdict.allowed else verdict.category

    def _latest_context(self, conversation_id: str, messages: list[dict]) -> dict | None:
        context = self.repo.get_latest_turn_context(conversation_id)
        if context:
            return context
        for item in reversed(messages):
            if item["role"] != "aisha":
                continue
            payload = self.repo.get_policy_response_payload(item["id"])
            if payload:
                return {
                    "message_id": item["id"],
                    "resolved_topic": None,
                    "payload": payload,
                }
        return None

    @staticmethod
    def _runtime_context(conversation, profile, previous, pending_offer) -> dict:
        latest = None
        if previous:
            latest = {
                "message_id": previous.get("message_id"),
                "dialogue_act": previous.get("dialogue_act"),
                "resolved_topic": previous.get("resolved_topic"),
                "response_type": (previous.get("payload") or {}).get("type"),
                "payload": previous.get("payload"),
            }
        pending = None
        if pending_offer:
            pending = {
                "offer_id": pending_offer["offer_id"],
                "topic": pending_offer["topic"],
                "resource_version": pending_offer["resource_version"],
                "policy_ids": pending_offer.get("policy_ids", []),
            }
        return {
            "conversation_id": conversation["conversation_id"],
            "simulated_date": conversation["simulated_date"],
            "confirmed_hire_profile": profile.model_dump(mode="json"),
            "latest_turn": latest,
            "pending_escalation_offer": pending,
        }

    @staticmethod
    def _redact(response):
        updates = {"text": redact_pii(response.text)}
        if isinstance(response, GroundedPolicyAnswer):
            updates["claims"] = [
                claim.model_copy(update={"text": redact_pii(claim.text)})
                for claim in response.claims
            ]
        return response.model_copy(update=updates)
