from datetime import date

from stai.medical import CertificateFields, validate_certificate_fields
from stai.models import ValidationStatus


def complete_fields(**changes):
    values = dict(
        patient_name="Alyssa M. Reyes",
        consultation_date="08/08/2026",
        issue_date="08/09/2026",
        absence_start_date="08/08/2026",
        absence_end_date="08/10/2026",
        duration_days=3,
        clinician_name="Dr. Sample Physician",
        facility_name="Synthetic Care Clinic",
        license_number_present=True,
        signature_present=True,
        recommendation_present=True,
    )
    values.update(changes)
    return CertificateFields(**values)


def test_complete_certificate_is_deterministic() -> None:
    result = validate_certificate_fields(complete_fields(), "Alyssa Reyes", date(2026, 8, 10))
    assert result.status == ValidationStatus.COMPLETE
    assert result.missing_codes == [] and result.inconsistency_codes == []


def test_missing_policy_required_field_is_incomplete() -> None:
    result = validate_certificate_fields(complete_fields(facility_name=None), "Alyssa Reyes", date(2026, 8, 10))
    assert result.status == ValidationStatus.INCOMPLETE
    assert result.missing_codes == ["facility_name"]


def test_closed_inconsistency_codes_cover_name_dates_and_duration() -> None:
    result = validate_certificate_fields(
        complete_fields(
            patient_name="Alice Reyes",
            consultation_date="08/11/2026",
            issue_date="08/09/2026",
            absence_end_date="08/09/2026",
            duration_days=5,
        ),
        "Alyssa Reyes",
        date(2026, 8, 10),
    )
    assert set(result.inconsistency_codes) == {
        "patient_name_mismatch",
        "issue_before_consultation",
        "consultation_after_evaluation_date",
        "duration_range_mismatch",
    }


def test_unrecognized_two_digit_year_requires_human_review_after_retry() -> None:
    result = validate_certificate_fields(
        complete_fields(issue_date="08/09/26"),
        "Alyssa Reyes",
        date(2026, 8, 10),
        retry_used=True,
    )
    assert result.status == ValidationStatus.NEEDS_HUMAN_REVIEW
    assert "unrecognized_date_format_after_retry" in result.review_codes


def test_low_required_field_confidence_requests_exactly_one_retry() -> None:
    fields = complete_fields(confidence={"clinician_name": 0.72})
    first = validate_certificate_fields(fields, "Alyssa Reyes", date(2026, 8, 10))
    assert first.retry_required is True and first.status is None
    second = validate_certificate_fields(fields, "Alyssa Reyes", date(2026, 8, 10), retry_used=True)
    assert second.retry_required is False
    assert second.status == ValidationStatus.NEEDS_HUMAN_REVIEW
    assert second.review_codes == ["low_confidence_after_retry"]

