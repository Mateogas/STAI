from datetime import date

from stai.medical import CertificateFields, validate_certificate_fields
from stai.models import ValidationStatus


def complete_fields(**changes):
    values = dict(
        patient_name="Juan Miguel Dela Cruz",
        consultation_date="05/15/2025",
        clinician_name="Dr. Maria Lourdes Santos",
        license_number_present=True,
        diagnosis_present=True,
    )
    values.update(changes)
    return CertificateFields(**values)


def test_complete_certificate_is_deterministic() -> None:
    result = validate_certificate_fields(complete_fields(), "Alyssa Reyes", date(2026, 8, 10))
    assert result.status == ValidationStatus.COMPLETE
    assert result.missing_codes == [] and result.inconsistency_codes == []


def test_missing_policy_required_field_is_incomplete() -> None:
    result = validate_certificate_fields(complete_fields(diagnosis_present=None), "Alyssa Reyes", date(2026, 8, 10))
    assert result.status == ValidationStatus.INCOMPLETE
    assert result.missing_codes == ["diagnosis"]


def test_consultation_after_the_evaluation_date_is_flagged() -> None:
    result = validate_certificate_fields(
        complete_fields(consultation_date="08/11/2026"),
        "Alyssa Reyes",
        date(2026, 8, 10),
    )
    assert result.status == ValidationStatus.INCOMPLETE
    assert result.inconsistency_codes == ["consultation_after_evaluation_date"]


def test_unrecognized_two_digit_year_requires_human_review_after_retry() -> None:
    result = validate_certificate_fields(
        complete_fields(consultation_date="08/09/26"),
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

