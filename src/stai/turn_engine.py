"""One deep turn-processing module for all AISHA policy conversations."""

from __future__ import annotations

import re
from collections.abc import Callable

from stai.guardrails import REFUSALS, redact_pii, validate_response_relevance
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
    ResolvedTurn,
)
from stai.policy import PolicyEngine, validate_claim_support
from stai.retriever import HandbookIndex, HandbookPageRecord, InMemoryHandbookIndex
from stai.state import Repo


AgentRunner = Callable[[ResolvedTurn, object, list[dict]], object | None]

_POLICY_ID = re.compile(r"\b(?:PAY|ACC|HRP)-\d{3}\b", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9-]+")
_TOPIC_TERMS: dict[OnboardingTopic, set[str]] = {
    OnboardingTopic.PAYROLL: {
        "pay", "payroll", "payslip", "salary", "wage", "deduction", "bank",
        "cutoff", "payday", "pay-period", "enrollment",
    },
    OnboardingTopic.RESOURCE_ACCESS: {
        "access", "account", "device", "laptop", "login", "password", "badge",
        "facility", "portal", "credential", "sandbox",
    },
    OnboardingTopic.HR_POLICIES: {
        "hr", "leave", "attendance", "dress", "conduct", "office", "hours",
        "holiday", "policy", "policies", "privacy",
    },
}
_HELP_TERMS = {"help", "human", "route", "support", "someone", "connect", "escalate", "escalation"}
_CONSENT_MESSAGES = {
    "yes", "yes please", "i consent", "yes route it", "route it",
    "route it please", "go ahead", "please proceed", "create the case", "send it",
}
_FOLLOW_UP_TERMS = {"it", "this", "that", "then", "one"}
_GREETINGS = {"hi", "hello", "hey", "thanks", "thank", "salamat"}


def _topic_for_policy_id(policy_id: str) -> OnboardingTopic:
    if policy_id.startswith("PAY-"):
        return OnboardingTopic.PAYROLL
    if policy_id.startswith("ACC-"):
        return OnboardingTopic.RESOURCE_ACCESS
    return OnboardingTopic.HR_POLICIES


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
        history_limit: int = 8,
    ) -> None:
        self.repo = repo
        self.records = records
        self.index = index or InMemoryHandbookIndex(records)
        self.agent_runner = agent_runner
        self.input_classifier = input_classifier
        self.history_limit = history_limit
        self.version = records[0].handbook_version if records else "1.0"

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

        if blocked_category:
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
            case = self.repo.consent_escalation_offer(
                pending_offer["offer_id"],
                expected_version=pending_offer["resource_version"],
            )
            response = EscalationConfirmation(
                text=(
                    "Your consented case was created and routed to "
                    f"{case['route_owner']} through {case['route_channel']}."
                ),
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.READY,
                case_id=case["case_id"],
                route_owner=case["route_owner"],
                route_channel=case["route_channel"],
                topic=resolved.topic or OnboardingTopic.HR_POLICIES,
                version=case["version"],
            )
            mode = ExecutionMode.DETERMINISTIC
        elif resolved.dialogue_act in {DialogueAct.HELP_REQUEST, DialogueAct.ESCALATION_REQUEST}:
            response = self._offer_escalation(
                conversation_id,
                user_message["id"],
                resolved,
                pending_offer,
            )
            mode = ExecutionMode.DETERMINISTIC
        elif resolved.dialogue_act == DialogueAct.CLARIFICATION:
            response = ClarificationRequest(
                text="Which onboarding area do you need help with: Payroll, Resource Access, or HR Policies?",
                handbook_version=self.version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.INSUFFICIENT,
                question="Which onboarding area do you need help with?",
                choices=["Payroll", "Resource Access", "HR Policies"],
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
            response, mode = self._answer_policy(resolved, profile, previous_messages, message)

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
        lowered = message.lower().strip()
        tokens = set(_WORD.findall(lowered))
        policy_ids = [match.group(0).upper() for match in _POLICY_ID.finditer(message)]
        explicit_topic = _topic_for_policy_id(policy_ids[0]) if policy_ids else None
        if not explicit_topic:
            matches = [topic for topic, terms in _TOPIC_TERMS.items() if tokens & terms]
            explicit_topic = matches[0] if len(matches) == 1 else None

        previous_topic = None
        previous_policy_ids: list[str] = []
        referenced_message_id = None
        if previous:
            if previous.get("resolved_topic"):
                previous_topic = OnboardingTopic(previous["resolved_topic"])
            payload = previous.get("payload") or {}
            previous_policy_ids = [item["policy_id"] for item in payload.get("citations", [])]
            referenced_message_id = previous.get("message_id")

        topic = explicit_topic or previous_topic
        normalized_consent = re.sub(r"[^a-z0-9 ]+", "", lowered)
        normalized_consent = " ".join(normalized_consent.split())
        if pending_offer and normalized_consent in _CONSENT_MESSAGES:
            return ResolvedTurn(
                dialogue_act=DialogueAct.CONSENT,
                topic=OnboardingTopic(pending_offer["topic"]),
                policy_ids=pending_offer.get("policy_ids", []),
                standalone_query=message,
                referenced_message_id=referenced_message_id,
            )

        help_requested = bool(tokens & _HELP_TERMS) or "talk to" in lowered
        if help_requested:
            return ResolvedTurn(
                dialogue_act=DialogueAct.CLARIFICATION if not topic else (
                    DialogueAct.ESCALATION_REQUEST
                    if tokens & {"route", "human", "connect", "escalate", "escalation"}
                    else DialogueAct.HELP_REQUEST
                ),
                topic=topic,
                policy_ids=policy_ids or previous_policy_ids,
                standalone_query=message,
                referenced_message_id=referenced_message_id,
            )

        if tokens and tokens <= _GREETINGS:
            act = DialogueAct.GREETING
        elif not topic and tokens & {"onboard", "onboarding", "setup", "orientation"}:
            act = DialogueAct.CLARIFICATION
        elif not topic:
            act = DialogueAct.UNSUPPORTED
        elif explicit_topic or policy_ids:
            act = DialogueAct.QUESTION
        else:
            act = DialogueAct.FOLLOW_UP if tokens & _FOLLOW_UP_TERMS or previous else DialogueAct.QUESTION

        query = message.strip()
        if topic and not explicit_topic:
            query = f"{topic.value.replace('_', ' ')} {query}"
        if (
            topic == OnboardingTopic.PAYROLL
            and not policy_ids
            and not (
                tokens
                & {
                    "details", "put", "update", "change", "onboard", "onboarding",
                    "payslip", "deduction", "cutoff", "date", "bank", "error",
                }
            )
        ):
            query = "PAY-001 payroll enrollment first pay schedule"
        # A contextual policy ID is a weak ranking hint, not authority and not a
        # hard filter. Explicit IDs remain exact retrieval constraints.
        return ResolvedTurn(
            dialogue_act=act,
            topic=topic,
            policy_ids=policy_ids,
            standalone_query=query,
            referenced_message_id=referenced_message_id if not explicit_topic else None,
        )

    def _answer_policy(self, resolved: ResolvedTurn, profile, messages: list[dict], current: str):
        preflight = None
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
                    preflight = self._preflight(resolved, profile)
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
        if preflight is None:
            preflight = self._preflight(resolved, profile)
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
        user_message_id: str,
        resolved: ResolvedTurn,
        pending_offer: dict | None,
    ) -> EscalationOffer:
        if pending_offer:
            payload = self.repo.get_escalation_offer(pending_offer["offer_id"])
            return EscalationOffer.model_validate(payload)
        topic = resolved.topic or OnboardingTopic.HR_POLICIES
        record = next(
            (
                item
                for item in self.records
                if item.policy_id in resolved.policy_ids and item.route
            ),
            None,
        )
        if not record:
            record = next((item for item in self.records if item.topic == topic.value and item.route), None)
        owner = (record.route if record and record.route else f"{topic.value}_support").replace("_", " ").title()
        label = topic.value.replace("_", " ").title()
        summary = f"Request help with {label} onboarding guidance."
        row = self.repo.create_escalation_offer(
            conversation_id,
            user_message_id,
            topic.value,
            owner,
            "Fictional HR Help Desk",
            summary,
            resolved.policy_ids,
        )
        return EscalationOffer(
            text="I can create this privacy-safe case after you review the summary and consent.",
            handbook_version=self.version,
            applicability=ApplicabilityStatus.APPLIES,
            evidence_state=EvidenceState.READY,
            offer_id=row["offer_id"],
            route_owner=owner,
            route_channel="Fictional HR Help Desk",
            proposed_summary=summary,
            topic=topic,
            version=row["version"],
        )

    @staticmethod
    def _redact(response):
        updates = {"text": redact_pii(response.text)}
        if isinstance(response, GroundedPolicyAnswer):
            updates["claims"] = [
                claim.model_copy(update={"text": redact_pii(claim.text)})
                for claim in response.claims
            ]
        return response.model_copy(update=updates)
