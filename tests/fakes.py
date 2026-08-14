"""Offline ReAct test double. Production never imports this module."""

from __future__ import annotations

from stai.agent import AgentRun
from stai.agentic_turn import AgenticPolicyTurn
from stai.clarifications import EvidenceGapAssessor
from stai.models import (
    Abstention,
    AgentTurnDecision,
    ApplicabilityStatus,
    ClarificationRequest,
    DialogueAct,
    EvidenceState,
    GroundedPolicyAnswer,
    PolicyCitation,
    PolicyClaim,
)
from stai.policy import PolicyEngine
from stai.tools import RunCapture


class OfflineReactRunner:
    """Legacy-semantic test double behind the new typed agent-runner contract."""

    def __init__(self, repo, records, handbook_index, **_kwargs):
        self.repo = repo
        self.records = records
        self.index = handbook_index
        self.planner = AgenticPolicyTurn()

    def available(self):
        return True

    def __call__(self, profile, messages, runtime_context):
        current = messages[-1]["text"]
        pending = runtime_context.get("pending_escalation_offer")
        previous = runtime_context.get("latest_turn")
        planning_text = (
            "Where is the official payroll route?"
            if "where is that payroll route" in current.lower()
            else current
        )
        plan = self.planner.plan(planning_text, previous, pending)
        capture = RunCapture(profile=profile)

        if plan.dialogue_act == DialogueAct.CONSENT:
            return self._decision(plan, capture, "case_action", current, case_action="consent_pending_offer")
        if plan.dialogue_act == DialogueAct.ACTION_STATUS:
            return self._decision(plan, capture, "case_action", current, case_action="report_case_status")
        if plan.dialogue_act == DialogueAct.CAPABILITY_DISCOVERY:
            return self._catalog(plan, capture)
        if plan.dialogue_act == DialogueAct.CLARIFICATION:
            question = plan.clarification_question or "Which onboarding area do you need help with?"
            return self._decision(
                plan,
                capture,
                "clarification_request",
                question,
                evidence_state="insufficient_evidence",
                question=question,
                choices=plan.clarification_choices or ["Payroll", "Resource Access", "HR Policies"],
            )
        if plan.dialogue_act in {
            DialogueAct.HELP_REQUEST,
            DialogueAct.ESCALATION_REQUEST,
            DialogueAct.GREETING,
            DialogueAct.UNSUPPORTED,
        }:
            plan = plan.model_copy(update={"policy_ids": []})
            if pending and plan.dialogue_act in {
                DialogueAct.HELP_REQUEST,
                DialogueAct.ESCALATION_REQUEST,
            }:
                return self._decision(
                    plan.model_copy(update={"dialogue_act": DialogueAct.ACTION_STATUS}),
                    capture,
                    "case_action",
                    current,
                    case_action="report_case_status",
                )
            return self._decision(
                plan,
                capture,
                "abstention",
                "Ask a specific Payroll, Resource Access, or HR Policies question first.",
                evidence_state="insufficient_evidence",
                reason="unresolved_ambiguity",
            )
        if any(
            phrase in current.lower()
            for phrase in ("training time paid", "overtime", "night work", "13th-month")
        ):
            return self._decision(
                plan,
                capture,
                "abstention",
                "The active handbook does not cover that payroll subject.",
                evidence_state="handbook_omission",
                reason="handbook_omission",
            )

        result = self.index.search(
            plan.standalone_query,
            profile,
            topic=plan.topic.value if plan.topic else None,
            policy_ids=set(plan.policy_ids),
        )
        for item in result.evidence:
            capture.record_evidence(item, self.records)
        gap = EvidenceGapAssessor().assess(plan.standalone_query, result)
        if gap.eligible:
            primary = result.evidence[0]
            return self._decision(
                plan,
                capture,
                "escalation_offer",
                "Partial evidence requires HR clarification.",
                evidence_state="insufficient_evidence",
                citations=[self._citation(primary)],
                gap_kind=gap.gap_kind.value,
                safe_known_text=gap.safe_known_text,
                unresolved_question=gap.unresolved_question,
                eligibility_reason=gap.reason,
            )
        response = PolicyEngine(self.records, index=self.index).answer(
            plan.standalone_query,
            profile,
            topic=plan.topic.value if plan.topic else None,
            policy_ids=set(plan.policy_ids),
            retrieval_result=result,
        )
        return self._from_response(plan, capture, response)

    def _catalog(self, plan, capture):
        records = [
            row for row in self.records
            if row.status == "active" and row.page_kind == "policy" and row.policy_id
            and (plan.catalog_scope is None or row.topic == plan.catalog_scope.value)
        ]
        for row in records:
            identity = (row.policy_id, row.handbook_version, row.page)
            capture.retrieved_identities.add(identity)
            capture.evidence_contents[identity] = row.content
        labels = {"payroll": "Payroll", "resource_access": "Resource Access", "hr_policies": "HR Policies"}
        sections = []
        for topic, label in labels.items():
            selected = [row for row in records if row.topic == topic]
            if selected:
                sections.append("**" + label + "**\n" + "\n".join(
                    f"- {row.policy_id} — {row.title.removesuffix(' - 1')}" for row in selected
                ))
        return self._decision(
            plan,
            capture,
            "grounded_answer",
            "\n\n".join(sections),
            citations=[self._record_citation(row) for row in records],
            claims=[PolicyClaim(text=row.content, citation_indexes=[i]).model_dump(mode="json") for i, row in enumerate(records)],
        )

    def _from_response(self, plan, capture, response):
        payload = response.model_dump(mode="json")
        response_type = payload.pop("type")
        payload.pop("clarifications", None)
        return self._decision(plan, capture, response_type, **payload)

    def _decision(self, plan, capture, response_type, text=None, **response):
        payload = plan.model_dump(mode="json")
        payload.update(
            response_type=response_type,
            text=text or response.pop("text"),
            handbook_version=response.pop("handbook_version", self.records[0].handbook_version),
            applicability=response.pop("applicability", ApplicabilityStatus.APPLIES.value),
            evidence_state=response.pop("evidence_state", EvidenceState.READY.value),
            **response,
        )
        return AgentRun(AgentTurnDecision.model_validate(payload), capture)

    @staticmethod
    def _citation(item):
        return {
            "policy_id": item.policy_id,
            "handbook_version": item.handbook_version,
            "page_start": item.page,
        }

    @staticmethod
    def _record_citation(row):
        return {
            "policy_id": row.policy_id,
            "handbook_version": row.handbook_version,
            "page_start": row.page,
        }
