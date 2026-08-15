"""Local ephemeral certificate extraction and deterministic validation."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Callable, Literal

from PIL import Image
from pydantic import BaseModel, Field

from stai.config import settings
from stai.handbook import ACTIVE_HANDBOOK_VERSION
from stai.models import ApplicabilityStatus, ValidationStatus
from stai.state import Repo


REQUIRED_TEXT_FIELDS = ("patient_name", "consultation_date", "clinician_name")


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
    diagnosis_present: bool | None = None
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


class CertificateAgentExecution(BaseModel):
    mode: Literal[
        "not_started", "react", "deterministic", "deterministic_degraded"
    ] = "not_started"
    actions: list[Literal[
        "confirm_certificate_policy",
        "run_local_ocr_validation",
        "validate_certificate_result",
        "persist_safe_result",
    ]] = Field(default_factory=list)


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
    validation_id: str | None = None
    handbook_version: str = ACTIVE_HANDBOOK_VERSION
    profile_revision: int | None = None
    attempt_count: int | None = None
    share_state: Literal["private", "shared"] | None = None
    version: int | None = None
    citations: list[dict] = Field(default_factory=list)
    retry_token: str | None = None
    retry_expires_at_utc: str | None = None
    manual_field_summary: dict[str, str] | None = None
    agent_execution: CertificateAgentExecution = Field(default_factory=CertificateAgentExecution)
    disclaimer: str = "Local completeness check only—not authenticity, approval, or medical assessment."
    official_hr_document_route: str = "Submit the original separately through the fictional Official HR Document Route."
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

    if settings.tesseract_cmd is not None:
        # Windows installers commonly update PATH only for newly opened shells.
        # An explicit local path keeps the already-running demo deterministic.
        pytesseract.pytesseract.tesseract_cmd = str(settings.tesseract_cmd)
    oriented = image.convert("RGB")
    return pytesseract.image_to_string(oriented, lang="eng")


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_DATE_NUMERIC = re.compile(r"(\d{2})[ /-](\d{2})[ /-](\d{4})")
_DATE_TEXT = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})")


def _date_value(raw: str | None) -> date | None:
    if not raw:
        return None
    stripped = raw.strip()
    if numeric := _DATE_NUMERIC.fullmatch(stripped):
        try:
            return date(int(numeric.group(3)), int(numeric.group(1)), int(numeric.group(2)))
        except ValueError:
            return None
    if textual := _DATE_TEXT.fullmatch(stripped):
        month = _MONTHS.get(textual.group(1).lower())
        if not month:
            return None
        try:
            return date(int(textual.group(3)), month, int(textual.group(2)))
        except ValueError:
            return None
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
    if fields.diagnosis_present is not True:
        missing.append("diagnosis")
    if fields.license_number_present is not True:
        missing.append("license_number")

    consultation = _date_value(fields.consultation_date)
    if fields.consultation_date and consultation is None:
        if not retry_used:
            return DeterministicValidation(retry_required=True)
        return DeterministicValidation(status=ValidationStatus.NEEDS_HUMAN_REVIEW, review_codes=["unrecognized_date_format_after_retry"])

    inconsistent = []
    if consultation and consultation > evaluation_date:
        inconsistent.append("consultation_after_evaluation_date")
    status = ValidationStatus.INCOMPLETE if missing or inconsistent else ValidationStatus.COMPLETE
    return DeterministicValidation(status=status, missing_codes=missing, inconsistency_codes=inconsistent, warning_codes=["retry_used"] if retry_used else [])


CERTIFICATE_POLICY_SUBAREA = "medical_certificate"


def resolve_certificate_applicability(records, profile) -> ApplicabilityStatus:
    """Resolve whether the governing certificate policy applies to this Hire.

    Finds the active policy page that governs medical certificates (by subarea,
    not a hardcoded ID) and evaluates its handbook applicability rules against
    the confirmed Hire Profile. Fails closed to human clarification when no
    governing policy is published.
    """
    from stai.policy import evaluate_applicability

    policy_record = next(
        (
            record
            for record in records
            if record.status == "active"
            and record.page_kind == "policy"
            and CERTIFICATE_POLICY_SUBAREA in (record.subareas or [])
        ),
        None,
    )
    if policy_record is None:
        return ApplicabilityStatus.NEEDS_CLARIFICATION
    return evaluate_applicability(policy_record, profile).status


class MedicalCheckService:
    def __init__(
        self,
        repo: Repo,
        *,
        extractor: Callable[[bytes, str], CertificateFields] | None = None,
        agent_runner=None,
    ) -> None:
        self.repo = repo
        self.extractor = extractor or self._default_extract
        self.agent_runner = agent_runner

    @staticmethod
    def _default_extract(data: bytes, kind: str) -> CertificateFields:
        return parse_certificate_text(extract_local_text(data, kind))

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
            cached: dict[str, DeterministicValidation] = {}

            def analyze() -> DeterministicValidation:
                if "validation" not in cached:
                    fields = self.extractor(data, preflight.kind or "pdf")
                    cached["validation"] = validate_certificate_fields(
                        fields,
                        "Alyssa Reyes",
                        evaluation_date,
                        retry_used=retry_used,
                    )
                return cached["validation"]

            run = None
            if self.agent_runner is not None:
                try:
                    run = self.agent_runner(analyze)
                except Exception:
                    run = None
            if run is not None and run.actions == [
                "confirm_certificate_policy",
                "run_local_ocr_validation",
            ]:
                validation = run.validation
                execution_mode = "react"
                actions = list(run.actions)
            else:
                validation = analyze()
                execution_mode = (
                    "deterministic"
                    if self.agent_runner is None
                    else "deterministic_degraded"
                )
                actions = ["confirm_certificate_policy", "run_local_ocr_validation"]
            actions.append("validate_certificate_result")
            execution = CertificateAgentExecution(mode=execution_mode, actions=actions)
            key = self.repo.ensure_installation_key()
            fingerprint = hmac.new(key, data, hashlib.sha256).hexdigest()
            if validation.retry_required:
                token = self.repo.create_retry_session(fingerprint)
                expiry = datetime.now(UTC) + timedelta(minutes=15)
                return MedicalCheckOutcome(
                    kind="retry_required",
                    code="low_confidence_or_unrecognized_date",
                    retry_token=token,
                    retry_expires_at_utc=expiry.isoformat().replace("+00:00", "Z"),
                    agent_execution=execution,
                )
            persisted_execution = CertificateAgentExecution(
                mode=execution_mode,
                actions=[*actions, "persist_safe_result"],
            )
            result = self.repo.create_validation_result(
                status=validation.status.value,
                missing_codes=validation.missing_codes,
                inconsistency_codes=validation.inconsistency_codes,
                warning_codes=validation.warning_codes,
                review_codes=validation.review_codes,
                evaluation_date=evaluation_date,
                fingerprint=fingerprint,
                attempt_count=2 if retry_used else 1,
                agent_execution=persisted_execution.model_dump(mode="json"),
            )
            return MedicalCheckOutcome(
                kind="validation_result",
                status=validation.status,
                missing_codes=validation.missing_codes,
                inconsistency_codes=validation.inconsistency_codes,
                warning_codes=validation.warning_codes,
                review_codes=validation.review_codes,
                validation_id=result["validation_id"],
                profile_revision=result["profile_revision"],
                attempt_count=result["accepted_attempt_count"],
                share_state=result["share_state"],
                version=result["resource_version"],
                citations=result["citations"],
                agent_execution=CertificateAgentExecution(**result["agent_execution"]),
                manual_field_summary=(
                    {name: "" for name in REQUIRED_TEXT_FIELDS}
                    if retry_used and validation.status == ValidationStatus.NEEDS_HUMAN_REVIEW else None
                ),
                fingerprint=fingerprint,
            )
        except Exception:
            return MedicalCheckOutcome(kind="check_failure", code="local_processing_failure")


_LABELS = {
    "patient_name": ("patient name",),
    "consultation_date": ("date of consultation", "consultation date"),
    "issue_date": ("issue date",),
    "absence_start_date": ("absence start date", "recommended rest from"),
    "absence_end_date": ("absence end date",),
    "duration_days": ("duration days",),
    "clinician_name": ("clinician name", "physician name"),
    "facility_name": ("facility name",),
}


def parse_certificate_text(text: str) -> CertificateFields:
    """Parse synthetic/demo certificate labels locally without retaining text.

    Presence-only fields (diagnosis, license, signature) never retain their
    underlying value, preserving the medical-content privacy boundary.
    """
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    values: dict[str, object] = {}
    ambiguous = False
    for field, labels in _LABELS.items():
        matches: list[str] = []
        for label in labels:
            matches.extend(re.findall(rf"(?im)^{re.escape(label)}\s*:\s*(.+?)\s*$", normalized))
        unique = list(dict.fromkeys(value.strip() for value in matches if value.strip()))
        if len(unique) > 1 and field not in {"consultation_date", "absence_start_date"}:
            ambiguous = True
        if unique:
            if field == "duration_days":
                number = re.search(r"\d+", unique[0])
                values[field] = int(number.group()) if number else None
            elif field in {"consultation_date", "absence_start_date"}:
                # "May 15, 2025 TO: May 17, 2025" style lines carry two dates.
                values[field] = re.split(r"\s+to\b", unique[0], flags=re.IGNORECASE)[0].strip()
            else:
                values[field] = unique[0]

    # Real certificates name the doctor inline ("Dr. Maria Lourdes Santos, MD")
    # rather than under a "Clinician Name:" label.
    if not values.get("clinician_name"):
        doctor = re.search(
            r"(?im)\bDr\.?\s+([A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+){1,3})\b",
            normalized,
        )
        if doctor:
            values["clinician_name"] = "Dr. " + doctor.group(1).strip()

    def present(label: str) -> bool | None:
        match = re.search(rf"(?im)^{re.escape(label)}\s*:\s*(.+?)\s*$", normalized)
        if not match:
            return None
        return match.group(1).strip().lower() not in {"no", "none", "absent", "false"}

    # License and diagnosis are presence-only. License appears as "License
    # Number:", "License No.:", or "PRC License No.:"; diagnosis as "Diagnosis:".
    license_present = bool(
        re.search(r"(?im)(?:prc\s+)?license\s+(?:no\.?|number)\s*:?\.?\s*[A-Za-z0-9\-]+", normalized)
    ) or present("license number")
    diagnosis_present = bool(re.search(r"(?im)^\s*diagnosis\s*:\s*\S+", normalized))

    values.update(
        license_number_present=license_present or None,
        signature_present=present("signature"),
        recommendation_present=present("recommendation"),
        diagnosis_present=diagnosis_present or None,
        extraction_ambiguous=ambiguous,
        unsupported_purpose=bool(re.search(r"(?i)laboratory result|prescription|diagnostic report", normalized)),
    )
    return CertificateFields(**values)
