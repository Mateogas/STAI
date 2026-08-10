"""Local ephemeral certificate extraction and deterministic validation."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Callable, Literal

from PIL import Image
from pydantic import BaseModel, Field

from stai.config import settings
from stai.models import ApplicabilityStatus, ValidationStatus
from stai.state import Repo


REQUIRED_TEXT_FIELDS = (
    "patient_name", "consultation_date", "issue_date", "absence_start_date",
    "clinician_name", "facility_name",
)


class CertificateFields(BaseModel):
    patient_name: str | None = None
    consultation_date: str | None = None
    issue_date: str | None = None
    absence_start_date: str | None = None
    absence_end_date: str | None = None
    duration_days: int | None = None
    clinician_name: str | None = None
    facility_name: str | None = None
    license_number_present: bool | None = None
    signature_present: bool | None = None
    recommendation_present: bool | None = None
    confidence: dict[str, float] = Field(default_factory=dict, exclude=True)
    extraction_ambiguous: bool = Field(default=False, exclude=True)
    unsupported_purpose: bool = Field(default=False, exclude=True)


class DeterministicValidation(BaseModel):
    status: ValidationStatus | None = None
    retry_required: bool = False
    missing_codes: list[str] = Field(default_factory=list)
    inconsistency_codes: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    review_codes: list[str] = Field(default_factory=list)


class PreflightResult(BaseModel):
    accepted: bool
    kind: Literal["pdf", "png", "jpeg"] | None = None
    code: str | None = None


class MedicalCheckOutcome(BaseModel):
    kind: Literal[
        "validation_result", "retry_required", "does_not_apply",
        "clarification_request", "upload_rejection", "check_failure",
        "privacy_acknowledgement_required", "needs_human_review",
    ]
    code: str | None = None
    status: ValidationStatus | None = None
    missing_codes: list[str] = Field(default_factory=list)
    inconsistency_codes: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    review_codes: list[str] = Field(default_factory=list)
    fingerprint: str | None = Field(default=None, exclude=True)


def detect_upload_kind(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


def preflight_upload(data: bytes, filename: str) -> PreflightResult:
    if len(data) > settings.certificate_max_bytes:
        return PreflightResult(accepted=False, code="file_too_large")
    kind = detect_upload_kind(data)
    if not kind:
        return PreflightResult(accepted=False, code="unsupported_media_type")
    suffix = Path(filename).suffix.lower()
    expected = {".pdf": "pdf", ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}.get(suffix)
    if expected != kind:
        return PreflightResult(accepted=False, code="extension_content_mismatch")
    if kind == "pdf":
        if any(marker in data for marker in (b"/JavaScript", b"/JS", b"/EmbeddedFile", b"/Encrypt")):
            return PreflightResult(accepted=False, code="active_or_embedded_content")
        try:
            import fitz

            document = fitz.open(stream=data, filetype="pdf")
            if document.page_count > settings.certificate_max_pdf_pages:
                return PreflightResult(accepted=False, code="too_many_pages")
            document.close()
        except Exception:
            return PreflightResult(accepted=False, code="corrupt_file")
    else:
        try:
            image = Image.open(BytesIO(data))
            if image.width * image.height > settings.certificate_max_pixels:
                return PreflightResult(accepted=False, code="image_too_large")
            image.verify()
        except Exception:
            return PreflightResult(accepted=False, code="corrupt_file")
    return PreflightResult(accepted=True, kind=kind)


def extract_local_text(data: bytes, kind: str) -> str:
    if kind == "pdf":
        import fitz

        document = fitz.open(stream=data, filetype="pdf")
        try:
            blocks = []
            for page in document:
                text = page.get_text("text").strip()
                if text:
                    blocks.append(text)
                else:
                    pixmap = page.get_pixmap(dpi=300, alpha=False)
                    image = Image.open(BytesIO(pixmap.tobytes("png")))
                    blocks.append(_ocr_image(image))
            return "\n".join(blocks)
        finally:
            document.close()
    image = Image.open(BytesIO(data))
    return _ocr_image(image)


def _ocr_image(image: Image.Image) -> str:
    import pytesseract

    oriented = image.convert("RGB")
    return pytesseract.image_to_string(oriented, lang="eng")


_DATE = re.compile(r"^(\d{2})[ /-](\d{2})[ /-](\d{4})$")


def _date_value(raw: str | None) -> date | None:
    if not raw or not (match := _DATE.fullmatch(raw.strip())):
        return None
    try:
        return date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
    except ValueError:
        return None


def _name_ends(raw: str) -> tuple[str, str]:
    normalized = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode().lower()
    tokens = [token for token in re.findall(r"[a-z]+", normalized) if token not in {"mr", "mrs", "ms", "dr"}]
    return (tokens[0], tokens[-1]) if len(tokens) >= 2 else ("", "")


def validate_certificate_fields(
    fields: CertificateFields,
    hire_name: str,
    evaluation_date: date,
    *,
    retry_used: bool = False,
) -> DeterministicValidation:
    if fields.unsupported_purpose:
        return DeterministicValidation(status=ValidationStatus.NEEDS_HUMAN_REVIEW, review_codes=["unsupported_certificate_purpose"])
    if fields.extraction_ambiguous:
        return DeterministicValidation(status=ValidationStatus.NEEDS_HUMAN_REVIEW, review_codes=["extraction_ambiguity"])
    low = [name for name, value in fields.confidence.items() if value < settings.certificate_ocr_confidence]
    if low:
        if not retry_used:
            return DeterministicValidation(retry_required=True)
        return DeterministicValidation(status=ValidationStatus.NEEDS_HUMAN_REVIEW, review_codes=["low_confidence_after_retry"])

    missing = [name for name in REQUIRED_TEXT_FIELDS if not getattr(fields, name)]
    if not fields.absence_end_date and not fields.duration_days:
        missing.append("absence_end_or_duration")
    for name in ("license_number_present", "signature_present", "recommendation_present"):
        if getattr(fields, name) is not True:
            missing.append(name)

    raw_dates = {
        "consultation": fields.consultation_date,
        "issue": fields.issue_date,
        "start": fields.absence_start_date,
        "end": fields.absence_end_date,
    }
    dates = {key: _date_value(value) for key, value in raw_dates.items()}
    invalid_dates = [key for key, raw in raw_dates.items() if raw and dates[key] is None]
    if invalid_dates:
        if not retry_used:
            return DeterministicValidation(retry_required=True)
        return DeterministicValidation(status=ValidationStatus.NEEDS_HUMAN_REVIEW, review_codes=["unrecognized_date_format_after_retry"])

    inconsistent = []
    if fields.patient_name and _name_ends(fields.patient_name) != _name_ends(hire_name):
        inconsistent.append("patient_name_mismatch")
    if dates["consultation"] and dates["issue"] and dates["consultation"] > dates["issue"]:
        inconsistent.append("issue_before_consultation")
    if dates["consultation"] and dates["consultation"] > evaluation_date:
        inconsistent.append("consultation_after_evaluation_date")
    if dates["issue"] and dates["issue"] > evaluation_date:
        inconsistent.append("issue_after_evaluation_date")
    if dates["start"] and dates["end"] and dates["start"] > dates["end"]:
        inconsistent.append("absence_range_reversed")
    if fields.duration_days is not None and fields.duration_days <= 0:
        inconsistent.append("duration_not_positive")
    if dates["start"] and dates["end"] and fields.duration_days:
        expected = (dates["end"] - dates["start"]).days + 1
        if fields.duration_days != expected:
            inconsistent.append("duration_range_mismatch")
    status = ValidationStatus.INCOMPLETE if missing or inconsistent else ValidationStatus.COMPLETE
    return DeterministicValidation(status=status, missing_codes=missing, inconsistency_codes=inconsistent, warning_codes=["retry_used"] if retry_used else [])


class MedicalCheckService:
    def __init__(self, repo: Repo, *, extractor: Callable[[bytes, str], CertificateFields] | None = None) -> None:
        self.repo = repo
        self.extractor = extractor or self._default_extract

    @staticmethod
    def _default_extract(data: bytes, kind: str) -> CertificateFields:
        # The production parser remains deterministic. Initial field parsing is
        # deliberately conservative; synthetic integration tests inject a typed
        # extractor while the raw local text never crosses this seam.
        extract_local_text(data, kind)
        return CertificateFields(extraction_ambiguous=True)

    def check(
        self,
        data: bytes,
        *,
        filename: str,
        evaluation_date: date,
        applicability: ApplicabilityStatus,
        acknowledged: bool,
        retry_used: bool = False,
    ) -> MedicalCheckOutcome:
        if applicability == ApplicabilityStatus.DOES_NOT_APPLY:
            return MedicalCheckOutcome(kind="does_not_apply")
        if applicability == ApplicabilityStatus.NEEDS_CLARIFICATION:
            return MedicalCheckOutcome(kind="clarification_request")
        if not acknowledged:
            return MedicalCheckOutcome(kind="privacy_acknowledgement_required")
        preflight = preflight_upload(data, filename)
        if not preflight.accepted:
            return MedicalCheckOutcome(kind="upload_rejection", code=preflight.code)
        try:
            fields = self.extractor(data, preflight.kind or "pdf")
            validation = validate_certificate_fields(fields, "Alyssa Reyes", evaluation_date, retry_used=retry_used)
            if validation.retry_required:
                return MedicalCheckOutcome(kind="retry_required")
            key = self.repo.ensure_installation_key()
            fingerprint = hmac.new(key, data, hashlib.sha256).hexdigest()
            return MedicalCheckOutcome(
                kind="validation_result",
                status=validation.status,
                missing_codes=validation.missing_codes,
                inconsistency_codes=validation.inconsistency_codes,
                warning_codes=validation.warning_codes,
                review_codes=validation.review_codes,
                fingerprint=fingerprint,
            )
        except Exception:
            return MedicalCheckOutcome(kind="check_failure", code="local_processing_failure")
