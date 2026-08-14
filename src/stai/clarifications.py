"""Evidence-gated HR clarification, resolution memory, and reviewed reuse."""

from __future__ import annotations

import re
import uuid
from datetime import date

from stai.models import (
    CaseResolutionInput,
    ClarificationReuseStatus,
    EscalationEligibility,
    EvidenceGapKind,
    GroundedPolicyAnswer,
    HumanClarificationReference,
    ResolutionScope,
    ResolutionType,
)
from stai.retriever import PolicyRetrievalResult, RetrievalOutcome
from stai.state import Repo, _utc_text


_TOKEN = re.compile(r"[a-z0-9-]+")
_STOPWORDS = {
    "a", "about", "against", "and", "are", "can", "could", "do", "does", "for",
    "every", "get", "happens", "have", "how", "i", "if", "in", "is", "it",
    "inside", "makes", "me", "my", "need", "of", "on", "one", "or", "please", "see",
    "that", "the", "then", "there", "this", "to", "using", "well", "what",
    "when", "where", "which", "with", "you",
}
_SUBJECT_ALIASES = {
    "day": {"date", "schedule", "timing"},
    "days": {"date", "schedule", "timing", "semi-monthly"},
    "paid": {"pay", "payroll", "schedule", "timing", "wages"},
    "payday": {"date", "pay", "schedule", "timing"},
    "next": {"following", "scheduled", "upcoming"},
    "wrong": {"correct", "correction", "change", "update"},
    "fix": {"correct", "correction", "change", "update"},
    "number": {"account", "details", "record"},
    "onboard": {"onboarding", "enrollment"},
    "medical": {"certificate", "diagnosis", "document"},
    "off": {"absence", "leave"},
    "photo": {"image", "jpg", "jpeg", "png"},
    "submit": {"upload", "use", "route", "accepts"},
    "late": {"delayed", "attendance"},
    "privacy": {"private", "personal", "data"},
    "accounts": {"account", "access", "device"},
    "laptops": {"laptop", "device", "devices"},
}
_EXCEPTION_TERMS = {
    "exception", "exceptions", "exempt", "exemption", "override", "waive",
    "waiver", "special-case", "special", "unusual",
}
_ROUTE_TERMS = {"route", "link", "url", "portal", "contact", "where"}
_PROCEDURE_TERMS = {
    "change", "correct", "correction", "details", "onboard", "onboarding",
    "fix", "put", "steps", "submit", "update",
}
_FOLLOW_UP_TERMS = {"explain", "mean", "means", "that", "this", "why"}
_GENERIC_DOMAIN_TERMS = {
    "answer", "handbook", "help", "hr", "laptop", "onboarding", "policy",
    "policies", "rule", "rules", "work", "laptops",
}


class EvidenceGapAssessor:
    """Decide whether partial eligible evidence warrants an HR clarification offer."""

    def assess(self, query: str, result: PolicyRetrievalResult) -> EscalationEligibility:
        if result.outcome == RetrievalOutcome.POLICY_CONFLICT and result.evidence:
            return EscalationEligibility(
                eligible=True,
                reason="applicable handbook records conflict and require human interpretation",
                gap_kind=EvidenceGapKind.POLICY_CONFLICT,
                safe_known_text="The active handbook contains conflicting applicable guidance.",
                unresolved_question=query,
                policy_ids=self._policy_ids(result),
            )
        if result.outcome != RetrievalOutcome.READY or not result.evidence:
            return EscalationEligibility(
                eligible=False,
                reason="no eligible partial policy evidence supports a clarification case",
            )

        tokens = set(_TOKEN.findall(query.lower()))
        evidence_text = " ".join(item.content for item in result.evidence).lower()
        gap_kind: EvidenceGapKind | None = None
        reason = "eligible evidence answers the question without a material clarification gap"

        if tokens & _EXCEPTION_TERMS or "what if" in query.lower():
            gap_kind = EvidenceGapKind.EXCEPTION_UNCLEAR
            reason = "the handbook provides the rule but does not authorize this exception"
        elif {"certificate", "day", "off"} <= tokens:
            gap_kind = EvidenceGapKind.MISSING_PROCEDURE
            reason = "the handbook defines certificate handling but not whether one day off requires a certificate"
        elif (
            tokens & _ROUTE_TERMS
            and "route" in evidence_text
            and not ({"portal", "contact", "link", "url"} & set(_TOKEN.findall(evidence_text)))
        ):
            gap_kind = EvidenceGapKind.ROUTE_UNCLEAR
            reason = "the handbook names a route but does not identify how to reach it"
        elif (
            tokens & _PROCEDURE_TERMS
            and ("route" in evidence_text or "guidance" in evidence_text)
            and not ("photo" in tokens and "photo" in evidence_text and "accepts" in evidence_text)
            and not any(item.page_kind == "procedure" and self._procedure_covers(tokens, item.content) for item in result.evidence)
        ):
            gap_kind = EvidenceGapKind.MISSING_PROCEDURE
            reason = "the handbook states the rule but does not provide the requested procedure"

        if gap_kind is None:
            return EscalationEligibility(eligible=False, reason=reason)

        primary = result.evidence[0]
        return EscalationEligibility(
            eligible=True,
            reason=reason,
            gap_kind=gap_kind,
            safe_known_text=primary.content,
            unresolved_question=query,
            policy_ids=self._policy_ids(result),
        )

    def covers_subject(self, query: str, result: PolicyRetrievalResult) -> bool:
        """Reject evidence that matches only generic topic words, not the asked subject."""
        if result.outcome != RetrievalOutcome.READY or not result.evidence:
            return False
        query_tokens = [
            token
            for token in _TOKEN.findall(query.lower())
            if token not in _STOPWORDS and token not in _GENERIC_DOMAIN_TERMS
            and not re.fullmatch(r"(?:pay|acc|hrp)-\d{3}", token)
        ]
        evidence_tokens = set(
            _TOKEN.findall(" ".join(item.content for item in result.evidence).lower())
        )
        uncovered = [
            token not in evidence_tokens
            and not (_SUBJECT_ALIASES.get(token, set()) & evidence_tokens)
            for token in query_tokens
        ]
        return not any(left and right for left, right in zip(uncovered, uncovered[1:]))

    @staticmethod
    def _policy_ids(result: PolicyRetrievalResult) -> list[str]:
        return list(dict.fromkeys(item.policy_id for item in result.evidence))

    @staticmethod
    def _procedure_covers(query_tokens: set[str], content: str) -> bool:
        content_tokens = set(_TOKEN.findall(content.lower()))
        material = query_tokens & _PROCEDURE_TERMS
        return bool(material & content_tokens) and bool(
            {"report", "portal", "contact", "submit", "through", "using"} & content_tokens
        )


class PolicyClarificationWorkflow:
    """Own structured resolution memory and its reviewed promotion lifecycle."""

    def __init__(self, repo: Repo) -> None:
        self.repo = repo

    def record_offer_gap(self, offer_id: str, decision: EscalationEligibility) -> None:
        if not decision.eligible or decision.gap_kind is None:
            raise ValueError("only an eligible evidence gap can be attached to an offer")
        with self.repo.connection() as conn:
            conn.execute(
                "INSERT INTO escalation_offer_evidence_gaps VALUES (?,?,?,?,?)",
                (
                    offer_id,
                    decision.gap_kind.value,
                    decision.safe_known_text or "",
                    decision.unresolved_question or "",
                    decision.reason,
                ),
            )

    def resolve(
        self,
        case_id: str,
        actor,
        resolution: CaseResolutionInput,
        *,
        expected_version: int,
    ) -> dict:
        from stai.cases import CaseActorRole, CaseWorkflow

        if actor.role != CaseActorRole.HR:
            raise PermissionError("only HR can resolve a case")
        self.repo.validate_policy_message(resolution.answer)
        now = _utc_text()
        if resolution.resolution_type == ResolutionType.POLICY_AMENDMENT_CANDIDATE:
            reuse_status = ClarificationReuseStatus.PENDING_HANDBOOK
        elif resolution.propose_for_reuse:
            reuse_status = ClarificationReuseStatus.PENDING_REVIEW
        else:
            reuse_status = ClarificationReuseStatus.THREAD_ONLY
        resolution_id = f"HRC-{uuid.uuid4().hex[:12].upper()}"

        with self.repo.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            case = CaseWorkflow._case_row(conn, case_id)
            if case["status"] != "open":
                raise ValueError("the case is already closed")
            if case["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            ordinal = int(
                conn.execute(
                    "SELECT COALESCE(MAX(ordinal),0)+1 FROM case_messages WHERE case_id=?",
                    (case_id,),
                ).fetchone()[0]
            )
            conn.execute(
                "INSERT INTO case_messages VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()), case_id, ordinal, "aisha", "aisha",
                    "shared", f"Based on HR's decision for this case: {resolution.answer}", None, now,
                ),
            )
            conn.execute(
                "INSERT INTO case_resolutions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)",
                (
                    resolution_id,
                    case_id,
                    resolution.resolution_type.value,
                    resolution.resolution_scope.value,
                    resolution.answer,
                    reuse_status.value,
                    resolution.effective_on.isoformat() if resolution.effective_on else None,
                    resolution.expires_on.isoformat() if resolution.expires_on else None,
                    actor.actor_id,
                    None,
                    now,
                    None,
                ),
            )
            conn.execute(
                "UPDATE escalation_cases SET status='closed',closed_at_utc=?,closing_hr_user=?,"
                "resource_version=resource_version+1 WHERE case_id=?",
                (now, actor.actor_id, case_id),
            )
            conn.execute(
                "UPDATE case_threads SET sharing_active=0,workflow_state='resolved',"
                "assigned_hr_user=?,resolution_summary=?,resolved_at_utc=? WHERE case_id=?",
                (actor.actor_id, resolution.answer, now, case_id),
            )
            CaseWorkflow._event(
                conn,
                case_id,
                "case_resolved",
                actor,
                {
                    "hire_visible": True,
                    "resolution_id": resolution_id,
                    "resolution_type": resolution.resolution_type.value,
                    "resolution_scope": resolution.resolution_scope.value,
                    "reuse_status": reuse_status.value,
                },
                now,
            )
            CaseWorkflow._notification(
                conn,
                case_id,
                "hire",
                case["hire_id"],
                "case_resolved",
                "Your HR support case was resolved",
                now,
            )
        return self.get_resolution(case_id) or {}

    def review(
        self,
        case_id: str,
        actor,
        *,
        approve: bool,
        expected_version: int,
    ) -> dict:
        from stai.cases import CaseActorRole, CaseWorkflow

        if actor.role != CaseActorRole.HR:
            raise PermissionError("only an HR policy owner can review a clarification")
        now = _utc_text()
        with self.repo.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM case_resolutions WHERE case_id=?", (case_id,)
            ).fetchone()
            if not row:
                raise KeyError("case resolution not found")
            if row["reuse_status"] != ClarificationReuseStatus.PENDING_REVIEW.value:
                raise ValueError("the resolution is not pending reuse review")
            if row["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            status = (
                ClarificationReuseStatus.APPROVED
                if approve
                else ClarificationReuseStatus.REJECTED
            )
            conn.execute(
                "UPDATE case_resolutions SET reuse_status=?,reviewed_by_hr_user=?,"
                "reviewed_at_utc=?,resource_version=resource_version+1 WHERE case_id=?",
                (status.value, actor.actor_id, now, case_id),
            )
            CaseWorkflow._event(
                conn,
                case_id,
                "clarification_reviewed",
                actor,
                {"reuse_status": status.value},
                now,
            )
        return self.get_resolution(case_id) or {}

    def get_resolution(self, case_id: str) -> dict | None:
        with self.repo.connection() as conn:
            row = conn.execute(
                "SELECT r.*,c.hire_id,c.topic,g.unresolved_question,g.safe_known_text "
                "FROM case_resolutions r JOIN escalation_cases c ON c.case_id=r.case_id "
                "LEFT JOIN case_evidence_gaps g ON g.case_id=r.case_id WHERE r.case_id=?",
                (case_id,),
            ).fetchone()
            if not row:
                return None
            policies = [
                item[0]
                for item in conn.execute(
                    "SELECT policy_id FROM escalation_case_policies WHERE case_id=? ORDER BY policy_id",
                    (case_id,),
                )
            ]
        return {**dict(row), "policy_ids": policies}

    def answer_thread(self, case_id: str, actor, question: str, *, expected_version: int) -> dict:
        from stai.cases import CaseActorRole, CaseWorkflow

        if actor.role != CaseActorRole.HIRE:
            raise PermissionError("only the Hire can ask a resolved-thread follow-up")
        clean = " ".join(question.split())
        if not clean or len(clean) > 4000:
            raise ValueError("question must contain 1 to 4000 characters")
        self.repo.validate_policy_message(clean)
        resolution = self.get_resolution(case_id)
        if not resolution:
            raise ValueError("the case has no structured resolution memory")
        if resolution["hire_id"] != actor.actor_id:
            raise PermissionError("the case belongs to another Hire")
        answer = self._thread_answer(clean, resolution)
        now = _utc_text()
        with self.repo.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            case = CaseWorkflow._case_row(conn, case_id)
            if case["status"] != "closed":
                raise ValueError("active cases remain conversations with HR")
            if case["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            ordinal = int(
                conn.execute(
                    "SELECT COALESCE(MAX(ordinal),0)+1 FROM case_messages WHERE case_id=?",
                    (case_id,),
                ).fetchone()[0]
            )
            conn.execute(
                "INSERT INTO case_messages VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), case_id, ordinal, "hire", actor.actor_id, "shared", clean, None, now),
            )
            conn.execute(
                "INSERT INTO case_messages VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), case_id, ordinal + 1, "aisha", "aisha", "shared", answer, None, now),
            )
            conn.execute(
                "UPDATE escalation_cases SET resource_version=resource_version+1 WHERE case_id=?",
                (case_id,),
            )
            CaseWorkflow._event(
                conn,
                case_id,
                "resolution_memory_used",
                actor,
                {"resolution_id": resolution["resolution_id"]},
                now,
            )
        return CaseWorkflow(self.repo).get_thread(case_id, actor)

    def find_approved(
        self,
        query: str,
        *,
        policy_ids: set[str],
        topic: str | None,
        hire_id: str,
        as_of: date,
    ) -> dict | None:
        with self.repo.connection() as conn:
            rows = conn.execute(
                "SELECT r.*,c.hire_id,c.topic,g.unresolved_question,g.safe_known_text "
                "FROM case_resolutions r JOIN escalation_cases c ON c.case_id=r.case_id "
                "LEFT JOIN case_evidence_gaps g ON g.case_id=r.case_id "
                "WHERE r.reuse_status='approved' AND r.resolution_type='policy_clarification' "
                "ORDER BY r.reviewed_at_utc DESC,r.resolution_id DESC"
            ).fetchall()
            for row in rows:
                if row["effective_on"] and date.fromisoformat(row["effective_on"]) > as_of:
                    continue
                if row["expires_on"] and date.fromisoformat(row["expires_on"]) < as_of:
                    continue
                if row["resolution_scope"] == ResolutionScope.HIRE.value and row["hire_id"] != hire_id:
                    continue
                if topic and row["topic"] != topic:
                    continue
                related = {
                    item[0]
                    for item in conn.execute(
                        "SELECT policy_id FROM escalation_case_policies WHERE case_id=?",
                        (row["case_id"],),
                    )
                }
                if policy_ids and not (policy_ids & related):
                    continue
                if not policy_ids and not self._textually_related(
                    query, " ".join((row["unresolved_question"] or "", row["answer"]))
                ):
                    continue
                return {**dict(row), "policy_ids": sorted(related)}
        return None

    @staticmethod
    def supplement(response: GroundedPolicyAnswer, clarification: dict) -> GroundedPolicyAnswer:
        reference = HumanClarificationReference(
            clarification_id=clarification["resolution_id"],
            source_case_id=clarification["case_id"],
            related_policy_ids=clarification["policy_ids"],
            resolution_scope=clarification["resolution_scope"],
            approved_at_utc=clarification["reviewed_at_utc"],
            expires_on=clarification["expires_on"],
        )
        text = (
            f"{response.text}\n\n**Reviewed HR clarification:** "
            f"{clarification['answer']} {reference.render()}\n\n"
            "This clarification supplements the cited handbook policy; it does not replace it."
        )
        return response.model_copy(
            update={
                "text": text,
                "clarifications": [*response.clarifications, reference],
            }
        )

    @staticmethod
    def _thread_answer(question: str, resolution: dict) -> str:
        if resolution["resolution_type"] == ResolutionType.UNABLE_TO_RESOLVE.value:
            return (
                "HR marked this case as unable to resolve, so I do not have an approved answer "
                "to reuse. Please start a new policy conversation if the situation changed."
            )
        source = " ".join(
            (resolution.get("unresolved_question") or "", resolution["answer"])
        )
        if not PolicyClarificationWorkflow._textually_related(question, source):
            return (
                "That question is outside this case's HR resolution. Please ask it in the "
                "parent policy conversation so AISHA can check the active handbook first."
            )
        scope = resolution["resolution_scope"].replace("_", " ")
        return (
            f"Based on HR's resolution for this case: {resolution['answer']}\n\n"
            f"Resolution scope: {scope}. This is Case Resolution Memory, not a replacement "
            "for the active handbook."
        )

    @staticmethod
    def _textually_related(left: str, right: str) -> bool:
        left_tokens = set(_TOKEN.findall(left.lower())) - _STOPWORDS
        right_tokens = set(_TOKEN.findall(right.lower())) - _STOPWORDS
        if left_tokens & _FOLLOW_UP_TERMS or not left_tokens:
            return True
        return len(left_tokens & right_tokens) >= 1
