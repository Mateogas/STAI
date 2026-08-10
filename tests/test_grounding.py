import pytest

from stai.models import (
    ApplicabilityStatus,
    GroundedPolicyAnswer,
    PolicyCitation,
    PolicyClaim,
)
from stai.policy import ClaimSupportError, validate_claim_support


def answer() -> GroundedPolicyAnswer:
    return GroundedPolicyAnswer(
        text="Policy claim [PAY-001 · AISHA Handbook v1.0 · p. 7]",
        handbook_version="1.0",
        applicability=ApplicabilityStatus.APPLIES,
        citations=[PolicyCitation(policy_id="PAY-001", handbook_version="1.0", page_start=7)],
        claims=[PolicyClaim(text="Policy claim", citation_indexes=[0])],
    )


def test_claim_support_accepts_exact_retrieved_identity() -> None:
    validate_claim_support(answer(), {("PAY-001", "1.0", 7)})


def test_claim_support_rejects_unretrieved_citation() -> None:
    with pytest.raises(ClaimSupportError):
        validate_claim_support(answer(), {("PAY-001", "1.0", 8)})


def test_claim_support_rejects_material_claim_without_citation() -> None:
    candidate = answer().model_copy(update={"claims": [PolicyClaim(text="Unsupported")]})
    with pytest.raises(ClaimSupportError):
        validate_claim_support(candidate, {("PAY-001", "1.0", 7)})

