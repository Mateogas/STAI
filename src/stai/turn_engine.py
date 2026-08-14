"""One deep turn-processing module for all AISHA policy conversations."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date

from stai.agentic_turn import AgenticPolicyTurn, topic_for_policy_id
from stai.guardrails import REFUSALS, redact_pii, validate_response_relevance
from stai.handbook import ACTIVE_HANDBOOK_VERSION
from stai.models import (
    Abstention,
    ApplicabilityStatus,
    ClarificationRequest,
    DialogueAct,
    EscalationConfirmation,
    EscalationOffer,
    EvidenceState,
    ExecutionMode,
    GroundedPolicyAnswer,
    OnboardingTopic,
    PolicyCitation,
    PolicyClaim,
    ResolvedTurn,
)
from stai.policy import PolicyEngine, validate_claim_support
from stai.retriever import HandbookIndex, HandbookPageRecord, InMemoryHandbookIndex
from stai.state import Repo


AgentRunner = Callable[[ResolvedTurn, object, list[dict]], object | None]


def _topic_for_policy_id(policy_id: str) -> OnboardingTopic:
    return topic_for_policy_id(policy_id)


class PolicyTurnEngine:
    """Resolve, execute, validate, and persist one bounded conversation turn."""

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
        evidence_gap_assessor=None,
        turn_planner=None,
        history_limit: int = 8,
    ) -> None:
        self.repo = repo
        self.records = records
        self.index = index or InMemoryHandbookIndex(records)
        self.agent_runner = agent_runner
        self.input_classifier = input_classifier
        if case_workflow is None:
            from stai.cases import CaseWorkflow

            case_workflow = CaseWorkflow(repo)
        if clarification_workflow is None or evidence_gap_assessor is None:
            from stai.clarifications import EvidenceGapAssessor, PolicyClarificationWorkflow

            clarification_workflow = clarification_workflow or PolicyClarificationWorkflow(repo)
            evidence_gap_assessor = evidence_gap_assessor or EvidenceGapAssessor()
        self.case_workflow = case_workflow
        self.clarification_workflow = clarification_workflow
        self.evidence_gap_assessor = evidence_gap_assessor
        self.turn_planner = turn_planner or AgenticPolicyTurn()
        self.history_limit = history_limit
        self.version = records[0].handbook_version if records else ACTIVE_HANDBOOK_VERSION

    def handle_turn(self, conversation_id: str, message: str):
        """The sole policy-turn interface used by transport callers and tests."""
        conversation = self.repo.get_policy_conversation(conversation_id)
        if not conversation:
            raise KeyError("conversation not found")
        self.repo.validate_policy_message(message)
        previous_messages = self.repo.list_policy_messages(conversation_id)[-self.history_limit :]
        previous_context = self._latest_context(conversation_id, previous_messages)
        pending_offer = self.repo.get_pending_escalation_offer_for_conversation(conversation_id)
        resolved = self._resolve(message, previous_context, pending_offer)
        blocked_category = self._blocked_category(message)
        user_message = self.repo.add_policy_message(conversation_id, "hire", message)
        profile = self.repo.get_hire_profile(conversation["hire_id"])

        contextual_consent = (
            resolved.dialogue_act == DialogueAct.CONSENT
            and pending_offer is not None
            and blocked_category == "off_topic"
        )
        if blocked_category and not contextual_consent:
            resolved = resolved.model_copy(update={"dialogue_act": DialogueAct.UNSUPPORTED})
            response = Abstention(
                text=REFUSALS[blocked_category],
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.INSUFFICIENT,
                reason="unsupported_topic",
            )
            mode = ExecutionMode.DETERMINISTIC
        elif resolved.dialogue_act == DialogueAct.CONSENT and pending_offer:
            from stai.cases import CaseActor

            case = self.case_workflow.consent_offer(
                conversation_id,
                pending_offer["offer_id"],
                expected_version=pending_offer["resource_version"],
                actor=CaseActor.hire(conversation["hire_id"]),
            )
            response = EscalationConfirmation(
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
                topic=resolved.topic or OnboardingTopic.HR_POLICIES,
                version=case["resource_version"],
            )
            mode = ExecutionMode.DETERMINISTIC
        elif resolved.dialogue_act in {DialogueAct.HELP_REQUEST, DialogueAct.ESCALATION_REQUEST}:
            response = self._offer_escalation(
                conversation_id,
                resolved,
                pending_offer,
            )
            mode = ExecutionMode.DETERMINISTIC
        elif resolved.dialogue_act == DialogueAct.ACTION_STATUS:
            response = self._case_status(conversation_id, pending_offer)
            mode = ExecutionMode.DETERMINISTIC
        elif resolved.dialogue_act == DialogueAct.CAPABILITY_DISCOVERY:
            response = self._policy_catalog(resolved.catalog_scope)
            mode = ExecutionMode.DETERMINISTIC
        elif resolved.dialogue_act == DialogueAct.CLARIFICATION:
            question = resolved.clarification_question or "Which onboarding area do you need help with?"
            choices = resolved.clarification_choices or ["Payroll", "Resource Access", "HR Policies"]
            response = ClarificationRequest(
                text=question + (f" Choose one: {', '.join(choices)}." if choices else ""),
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.INSUFFICIENT,
                question=question,
                choices=choices,
            )
            mode = ExecutionMode.DETERMINISTIC
        elif resolved.dialogue_act in {DialogueAct.UNSUPPORTED, DialogueAct.GREETING}:
            text = (
                "Hello—I'm AISHA. I can help with Payroll, Resource Access, or HR Policies."
                if resolved.dialogue_act == DialogueAct.GREETING
                else "This demo is limited to Payroll, Resource Access, and HR Policies."
            )
            response = Abstention(
                text=text,
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.INSUFFICIENT,
                reason="unsupported_topic",
            )
            mode = ExecutionMode.DETERMINISTIC
        else:
            response, mode = self._answer_policy(
                conversation_id,
                user_message["id"],
                resolved,
                profile,
                previous_messages,
                message,
                as_of=date.fromisoformat(conversation["simulated_date"]),
            )

        response = self._redact(response)
        self.repo.save_policy_response(
            conversation_id,
            response,
            dialogue_act=resolved.dialogue_act.value,
            resolved_topic=resolved.topic.value if resolved.topic else None,
            referenced_message_id=resolved.referenced_message_id,
            execution_mode=mode.value,
        )
        return response

    def _blocked_category(self, message: str) -> str | None:
        lowered = message.lower()
        injection_markers = (
            "ignore all previous", "ignore previous instructions", "reveal your system",
            "show your system prompt", "you are now dan", "override your rules",
            "ignore the handbook",
        )
        if any(marker in lowered for marker in injection_markers):
            return "injection"
        if not self.input_classifier:
            return None
        try:
            verdict = self.input_classifier(message)
        except Exception:
            return None
        return None if verdict.allowed else verdict.category

    def _latest_context(self, conversation_id: str, messages: list[dict]) -> dict | None:
        context = self.repo.get_latest_turn_context(conversation_id)
        if context:
            return context
        for item in reversed(messages):
            if item["role"] != "aisha":
                continue
            payload = self.repo.get_policy_response_payload(item["id"])
            if not payload:
                continue
            policy_ids = [citation["policy_id"] for citation in payload.get("citations", [])]
            topic = _topic_for_policy_id(policy_ids[0]).value if policy_ids else None
            return {
                "message_id": item["id"],
                "resolved_topic": topic,
                "payload": payload,
            }
        return None

    def _resolve(self, message: str, previous: dict | None, pending_offer: dict | None) -> ResolvedTurn:
        return self.turn_planner.plan(message, previous, pending_offer)

    def _answer_policy(
        self,
        conversation_id: str,
        user_message_id: str,
        resolved: ResolvedTurn,
        profile,
        messages: list[dict],
        current: str,
        *,
        as_of: date,
    ):
        preflight = self._preflight(resolved, profile)
        if (
            preflight.outcome.value == "ready"
            and not self.evidence_gap_assessor.covers_subject(resolved.standalone_query, preflight)
        ):
            return (
                Abstention(
                    text=(
                        "The active handbook does not cover the specific subject in this "
                        "question. No HR ticket was offered because there is no eligible "
                        "partial policy evidence to clarify."
                    ),
                    handbook_version=self.version,
                    applicability=ApplicabilityStatus.APPLIES,
                    evidence_state=EvidenceState.HANDBOOK_OMISSION,
                    reason="handbook_omission",
                ),
                ExecutionMode.DETERMINISTIC,
            )
        gap = self.evidence_gap_assessor.assess(resolved.standalone_query, preflight)
        approved = None
        if gap.eligible:
            approved = self.clarification_workflow.find_approved(
                resolved.standalone_query,
                policy_ids=set(gap.policy_ids),
                topic=resolved.topic.value if resolved.topic else None,
                hire_id=profile.employee_id,
                as_of=as_of,
            )
            if not approved:
                return (
                    self._offer_evidence_gap(
                        conversation_id,
                        user_message_id,
                        resolved,
                        preflight,
                        gap,
                    ),
                    ExecutionMode.DETERMINISTIC,
                )
        elif not self.evidence_gap_assessor.covers_subject(resolved.standalone_query, preflight):
            return (
                Abstention(
                    text=(
                        "The active handbook does not cover the specific subject in this "
                        "question. No HR ticket was offered because there is no eligible "
                        "partial policy evidence to clarify."
                    ),
                    handbook_version=self.version,
                    applicability=ApplicabilityStatus.APPLIES,
                    evidence_state=EvidenceState.HANDBOOK_OMISSION,
                    reason="handbook_omission",
                ),
                ExecutionMode.DETERMINISTIC,
            )
        if approved:
            base = PolicyEngine(self.records, index=self.index).answer(
                resolved.standalone_query,
                profile,
                topic=resolved.topic.value if resolved.topic else None,
                policy_ids=set(resolved.policy_ids),
                retrieval_result=preflight,
            )
            if isinstance(base, GroundedPolicyAnswer):
                return self.clarification_workflow.supplement(base, approved), ExecutionMode.DETERMINISTIC
        if self.agent_runner:
            try:
                run_result = self.agent_runner(
                    resolved,
                    profile,
                    [*messages, {"role": "hire", "text": current}],
                )
                if isinstance(run_result, tuple):
                    candidate, eligible_identities = run_result
                else:
                    candidate = run_result
                    eligible_identities = self._identities(preflight)
                if candidate and candidate.type != "abstention":
                    if isinstance(candidate, GroundedPolicyAnswer):
                        validate_claim_support(candidate, eligible_identities)
                    validate_response_relevance(
                        candidate,
                        resolved.topic.value if resolved.topic else None,
                        self.records,
                    )
                    return candidate, ExecutionMode.AGENT
            except Exception:
                pass
        response = PolicyEngine(self.records, index=self.index).answer(
            resolved.standalone_query,
            profile,
            topic=resolved.topic.value if resolved.topic else None,
            policy_ids=set(resolved.policy_ids),
            retrieval_result=preflight,
        )
        validate_response_relevance(
            response,
            resolved.topic.value if resolved.topic else None,
            self.records,
        )
        mode = (
            ExecutionMode.DEGRADED
            if self.agent_runner is not None
            else ExecutionMode.DETERMINISTIC
        )
        return response, mode

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
                "I can't find a case created in this conversation. Tell me which onboarding "
                "area needs human support and I can prepare a consent-based request."
            ),
            handbook_version=self.version,
            applicability=ApplicabilityStatus.APPLIES,
            evidence_state=EvidenceState.INSUFFICIENT,
            question="Which onboarding area needs human support?",
            choices=["Payroll", "Resource Access", "HR Policies"],
        )

    def _policy_catalog(self, scope: OnboardingTopic | None = None) -> GroundedPolicyAnswer:
        labels = {
            OnboardingTopic.PAYROLL: "Payroll",
            OnboardingTopic.RESOURCE_ACCESS: "Resource Access",
            OnboardingTopic.HR_POLICIES: "HR Policies",
        }
        selected_labels = {
            topic: label for topic, label in labels.items() if scope is None or topic == scope
        }
        policy_pages = {
            topic: sorted(
                (
                    record
                    for record in self.records
                    if record.status == "active"
                    and record.page_kind == "policy"
                    and record.topic == topic.value
                    and record.policy_id
                ),
                key=lambda record: record.policy_id or "",
            )
            for topic in selected_labels
        }
        citations = []
        claims = []
        sections = [
            "You can ask about these active handbook policies. AISHA will check whether "
            "a policy applies to your confirmed Hire Profile:"
        ]
        for topic, label in selected_labels.items():
            records = policy_pages[topic]
            start = len(citations)
            bullets = []
            for record in records:
                citation = PolicyCitation(
                    policy_id=record.policy_id or "",
                    handbook_version=record.handbook_version,
                    page_start=record.page,
                )
                citations.append(citation)
                title = re.sub(r"\s+-\s+1$", "", record.title)
                bullets.append(f"- {record.policy_id} — {title} {citation.render()}")
            sections.append(f"**{label}**\n" + "\n".join(bullets))
            claims.append(
                PolicyClaim(
                    text=f"{label} includes " + ", ".join(record.policy_id or "" for record in records) + ".",
                    citation_indexes=list(range(start, len(citations))),
                )
            )
        sections.append(
            "You can ask what a policy means, what steps it requires, whether it applies "
            "to your confirmed profile, or how to request human support."
        )
        response = GroundedPolicyAnswer(
            text="\n\n".join(sections),
            handbook_version=self.version,
            applicability=ApplicabilityStatus.APPLIES,
            evidence_state=EvidenceState.READY,
            citations=citations,
            claims=claims,
        )
        validate_claim_support(
            response,
            {
                (record.policy_id or "", record.handbook_version, record.page)
                for records in policy_pages.values()
                for record in records
            },
        )
        return response

    def _preflight(self, resolved: ResolvedTurn, profile):
        return self.index.search(
            resolved.standalone_query,
            profile,
            topic=resolved.topic.value if resolved.topic else None,
            policy_ids=set(resolved.policy_ids),
        )

    @staticmethod
    def _identities(retrieval_result) -> set[tuple[str, str, int]]:
        return {
            (item.policy_id, item.handbook_version, item.page)
            for item in retrieval_result.evidence
        }

    def _offer_escalation(
        self,
        conversation_id: str,
        resolved: ResolvedTurn,
        pending_offer: dict | None,
    ):
        if pending_offer:
            return self._pending_offer_response(pending_offer)
        from stai.cases import CaseActor

        existing = next(
            (
                case
                for case in self.case_workflow.list_cases(
                    CaseActor.hire(), parent_conversation_id=conversation_id
                )
                if case["status"] == "open"
                and (resolved.topic is None or case["topic"] == resolved.topic.value)
            ),
            None,
        )
        if existing:
            return EscalationConfirmation(
                text=(
                    f"An open HR clarification ticket already covers this conversation: "
                    f"case {existing['case_id']}. Continue there instead of creating a duplicate."
                ),
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.READY,
                case_id=existing["case_id"],
                route_owner=existing["route_owner"],
                route_channel=existing["route_channel"],
                topic=OnboardingTopic(existing["topic"]),
                version=existing["resource_version"],
            )
        return Abstention(
            text=(
                "I can create an HR clarification ticket only when eligible handbook evidence "
                "answers part of a specific question but leaves a material gap. Ask the policy "
                "question first, and I will offer HR when that condition is met."
            ),
            handbook_version=self.version,
            applicability=ApplicabilityStatus.APPLIES,
            evidence_state=EvidenceState.INSUFFICIENT,
            reason="unresolved_ambiguity",
        )

    def _offer_evidence_gap(
        self,
        conversation_id: str,
        user_message_id: str,
        resolved: ResolvedTurn,
        retrieval_result,
        gap,
    ):
        pending = self.repo.get_pending_escalation_offer_for_conversation(conversation_id)
        if pending:
            return self._pending_offer_response(pending)
        from stai.cases import CaseActor

        existing = next(
            (
                case
                for case in self.case_workflow.list_cases(
                    CaseActor.hire(), parent_conversation_id=conversation_id
                )
                if case["status"] == "open" and case["topic"] == (resolved.topic or OnboardingTopic.HR_POLICIES).value
            ),
            None,
        )
        if existing:
            return EscalationConfirmation(
                text=(
                    f"An open HR clarification ticket already covers this conversation: "
                    f"case {existing['case_id']}. Continue there instead of creating a duplicate."
                ),
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.READY,
                case_id=existing["case_id"],
                route_owner=existing["route_owner"],
                route_channel=existing["route_channel"],
                topic=OnboardingTopic(existing["topic"]),
                version=existing["resource_version"],
            )
        topic = resolved.topic or OnboardingTopic.HR_POLICIES
        with self.repo.connection() as conn:
            prior_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM escalation_cases c JOIN case_threads t ON t.case_id=c.case_id "
                    "WHERE t.parent_conversation_id=? AND c.topic=?",
                    (conversation_id, topic.value),
                ).fetchone()[0]
            )
        if prior_count >= 2:
            return Abstention(
                text=(
                    "This conversation has already used the allowed HR clarification tickets "
                    "for this topic. Continue an existing ticket or start a new focused conversation."
                ),
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.INSUFFICIENT,
                reason="unresolved_ambiguity",
            )
        record = next(
            (
                item
                for item in self.records
                if item.policy_id in gap.policy_ids and item.route
            ),
            None,
        )
        if not record:
            record = next((item for item in self.records if item.topic == topic.value and item.route), None)
        owner = (record.route if record and record.route else f"{topic.value}_support").replace("_", " ").title()
        label = topic.value.replace("_", " ").title()
        question = gap.unresolved_question or resolved.standalone_query
        summary = f"Clarify {gap.gap_kind.value.replace('_', ' ')}: {question}"[:500]
        policy_ids = gap.policy_ids or ([record.policy_id] if record and record.policy_id else [])
        row = self.repo.create_escalation_offer(
            conversation_id,
            user_message_id,
            topic.value,
            owner,
            "Fictional HR Help Desk",
            summary,
            policy_ids,
        )
        self.clarification_workflow.record_offer_gap(row["offer_id"], gap)
        primary = retrieval_result.evidence[0]
        citation = PolicyCitation(
            policy_id=primary.policy_id,
            handbook_version=primary.handbook_version,
            page_start=primary.page,
        )
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
                    item
                    for item in self.records
                    if item.policy_id in pending["policy_ids"]
                    and item.content == payload.get("safe_known_text")
                ),
                None,
            )
            if not record:
                record = next(
                    (
                        item
                        for item in self.records
                        if item.policy_id in pending["policy_ids"] and item.page_kind == "policy"
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

    @staticmethod
    def _redact(response):
        updates = {"text": redact_pii(response.text)}
        if isinstance(response, GroundedPolicyAnswer):
            updates["claims"] = [
                claim.model_copy(update={"text": redact_pii(claim.text)})
                for claim in response.claims
            ]
        return response.model_copy(update=updates)
