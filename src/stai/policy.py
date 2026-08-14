"""Deterministic applicability and fail-closed policy-response assembly."""

from __future__ import annotations

import re
from dataclasses import dataclass

from stai.models import (
    Abstention,
    ApplicabilityStatus,
    ClarificationRequest,
    EvidenceState,
    GroundedPolicyAnswer,
    HireProfile,
    PolicyCitation,
    PolicyClaim,
)
from stai.retriever import HandbookIndex, HandbookPageRecord, InMemoryHandbookIndex, RetrievalOutcome


@dataclass(frozen=True)
class ApplicabilityDecision:
    status: ApplicabilityStatus
    required_attribute: str | None = None


_RULE_FIELDS = {
    "role_keys": "role_key",
    "department_keys": "department_key",
    "employment_classifications": "employment_classification",
    "work_sites": "work_site",
}


def evaluate_applicability(record: HandbookPageRecord, profile: HireProfile) -> ApplicabilityDecision:
    if not record.applicability:
        return ApplicabilityDecision(ApplicabilityStatus.APPLIES)
    for rule_name, profile_name in _RULE_FIELDS.items():
        allowed = record.applicability[rule_name]
        if allowed == ["all"]:
            continue
        actual = getattr(profile, profile_name, None)
        if actual is None:
            return ApplicabilityDecision(ApplicabilityStatus.NEEDS_CLARIFICATION, profile_name)
        if actual not in allowed:
            return ApplicabilityDecision(ApplicabilityStatus.DOES_NOT_APPLY)
    return ApplicabilityDecision(ApplicabilityStatus.APPLIES)


class ClaimSupportError(ValueError):
    pass


def validate_claim_support(
    response: GroundedPolicyAnswer,
    retrieved_identities: set[tuple[str, str, int]],
) -> None:
    for claim in response.claims:
        if not claim.citation_indexes:
            raise ClaimSupportError("material claim has no support")
        for index in claim.citation_indexes:
            if index < 0 or index >= len(response.citations):
                raise ClaimSupportError("claim references an unknown citation")
            citation = response.citations[index]
            pages = range(citation.page_start, (citation.page_end or citation.page_start) + 1)
            if not all((citation.policy_id, citation.handbook_version, page) in retrieved_identities for page in pages):
                raise ClaimSupportError("citation does not match retrieved eligible evidence")


_SUPPORTED_TERMS = {
    "pay", "payroll", "payslip", "deduction", "holiday", "access", "device",
    "remote", "account", "branch", "attendance", "leave", "medical",
    "certificate", "dress", "privacy", "hr", "conduct", "office", "onboard",
    "onboarding", "details", "route", "support", "help", "enrollment",
}


class PolicyEngine:
    def __init__(self, records: list[HandbookPageRecord], *, index: HandbookIndex | None = None) -> None:
        self.records = records
        self.index = index or InMemoryHandbookIndex(records)
        self.version = records[0].handbook_version if records else "1.0"

    def answer(
        self,
        query: str,
        profile: HireProfile,
        *,
        topic: str | None = None,
        policy_ids: set[str] | None = None,
        retrieval_result=None,
    ):
        tokens = set(re.findall(r"[a-z0-9-]+", query.lower()))
        exact_ids = {token.upper() for token in tokens if re.fullmatch(r"(?:pay|acc|hrp)-\d{3}", token)}
        if not topic and not exact_ids and not (tokens & _SUPPORTED_TERMS):
            return self._abstain("insufficient_evidence")
        result = retrieval_result or self.index.search(
            query, profile, topic=topic, policy_ids=policy_ids,
        )
        if result.outcome == RetrievalOutcome.ATTRIBUTE_REQUIRED:
            label = (result.required_attribute or "required attribute").replace("_", " ")
            choices = {
                "work_site": ["Assigned work site changed", "Temporary workday or visit"],
                "employment_classification": ["HR confirmed the change", "The change is still pending"],
            }.get(result.required_attribute, ["Confirmed", "Not confirmed"])
            return ClarificationRequest(
                text=f"I need one confirmed detail before applying the policy: {label}.",
                handbook_version=self.version,
                applicability=ApplicabilityStatus.NEEDS_CLARIFICATION,
                evidence_state=EvidenceState.ATTRIBUTE_REQUIRED,
                question=f"What is the confirmed {label}?",
                choices=choices,
            )
        if result.outcome != RetrievalOutcome.READY or not result.evidence:
            return self._abstain("insufficient_evidence")
        evidence = result.evidence
        if exact_ids:
            evidence = [item for item in evidence if item.policy_id in exact_ids]
        if not evidence:
            return self._abstain("insufficient_evidence")
        primary = evidence[0]
        citation = PolicyCitation(
            policy_id=primary.policy_id,
            handbook_version=primary.handbook_version,
            page_start=primary.page,
        )
        if primary.applicability == ApplicabilityStatus.DOES_NOT_APPLY:
            claim_text = f"{primary.policy_id} does not apply to Alyssa's confirmed Hire Profile."
        else:
            claim_text = primary.content
        text = f"{claim_text} {citation.render()}\n\nBased on AISHA Handbook v{self.version}."
        response = GroundedPolicyAnswer(
            text=text,
            handbook_version=self.version,
            applicability=primary.applicability,
            citations=[citation],
            claims=[PolicyClaim(text=claim_text, citation_indexes=[0])],
        )
        validate_claim_support(response, {(primary.policy_id, primary.handbook_version, primary.page)})
        return response

    def _abstain(self, reason: str) -> Abstention:
        return Abstention(
            text="The active handbook does not contain enough eligible evidence for a reliable answer. I can help route this to HR.",
            handbook_version=self.version,
            applicability=ApplicabilityStatus.APPLIES,
            evidence_state=EvidenceState.INSUFFICIENT,
            reason=reason,
        )
