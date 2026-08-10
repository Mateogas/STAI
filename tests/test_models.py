from datetime import date

import pytest
from pydantic import TypeAdapter, ValidationError

from stai.models import (
    Abstention,
    ApplicabilityStatus,
    ClarificationRequest,
    EscalationOffer,
    GroundedPolicyAnswer,
    HireProfile,
    OnboardingTopic,
    PolicyCitation,
    PolicyResponse,
    ValidationResult,
    ValidationStatus,
)


def test_alyssa_profile_uses_closed_applicability_keys() -> None:
    profile = HireProfile.alyssa()
    assert profile.employee_id == "emp-alyssa"
    assert profile.role_key == "branch_banking_associate"
    assert profile.department_key == "branch_banking"
    assert profile.employment_classification == "probationary"
    assert profile.work_site == "branch"


def test_all_four_policy_responses_are_discriminated() -> None:
    citation = PolicyCitation(policy_id="PAY-001", handbook_version="1.0", page_start=12)
    payloads = [
        GroundedPolicyAnswer(
            text="Pay dates follow the published schedule.",
            handbook_version="1.0",
            applicability=ApplicabilityStatus.APPLIES,
            citations=[citation],
        ),
        ClarificationRequest(
            text="Is remote your assigned work site or only temporary?",
            handbook_version="1.0",
            applicability=ApplicabilityStatus.NEEDS_CLARIFICATION,
            question="Is remote your assigned work site?",
            choices=["Assigned work site", "Temporary workday"],
        ),
        Abstention(
            text="The active handbook does not support a conclusion.",
            handbook_version="1.0",
            applicability=ApplicabilityStatus.APPLIES,
            reason="insufficient_evidence",
        ),
        EscalationOffer(
            text="I can route this to HR after you consent.",
            handbook_version="1.0",
            applicability=ApplicabilityStatus.APPLIES,
            offer_id="offer-1",
            route_owner="HR",
            route_channel="HR Help Desk",
            proposed_summary="Clarify the applicable payroll rule.",
            topic=OnboardingTopic.PAYROLL,
        ),
    ]
    adapter = TypeAdapter(PolicyResponse)
    assert [adapter.validate_python(item.model_dump()).type for item in payloads] == [
        "grounded_answer",
        "clarification_request",
        "abstention",
        "escalation_offer",
    ]


def test_policy_citation_rejects_filename_and_invalid_page_range() -> None:
    with pytest.raises(ValidationError):
        PolicyCitation(policy_id="leave_policy.md", handbook_version="1.0", page_start=1)
    with pytest.raises(ValidationError):
        PolicyCitation(
            policy_id="HRP-004", handbook_version="1.0", page_start=15, page_end=14
        )


def test_validation_result_contains_codes_not_medical_content() -> None:
    result = ValidationResult(
        validation_id="val-1",
        employee_id="emp-alyssa",
        status=ValidationStatus.INCOMPLETE,
        policy_id="HRP-004",
        handbook_version="1.0",
        profile_revision=1,
        missing_codes=["clinician_license_number"],
        evaluation_date=date(2026, 8, 10),
        citations=[
            PolicyCitation(policy_id="HRP-004", handbook_version="1.0", page_start=75)
        ],
    )
    dumped = result.model_dump_json()
    assert "diagnosis" not in dumped
    assert "filename" not in dumped
    assert "clinician_license_number" in dumped

