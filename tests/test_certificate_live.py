"""Live proof that the central certificate feature works end to end.

Unlike the policy-agent live suite, these tests need no Ollama: the certificate
flow is deterministic. They exercise the *real* extraction pipeline (PyMuPDF
text layer and, when available, real Tesseract OCR) end to end through
``MedicalCheckService`` and assert both the correct policy-aware outcome and the
privacy boundary (no document content is ever persisted).

The PDF-text tests always run. The image-OCR test skips when the Tesseract
binary is unavailable, so the suite stays green on machines without it.
"""

from __future__ import annotations

import json
from datetime import date
from io import BytesIO

import pytest

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen.canvas import Canvas

from stai.config import settings
from stai.medical import MedicalCheckService, resolve_certificate_applicability
from stai.models import ApplicabilityStatus, ValidationStatus
from stai.retriever import load_page_records
from stai.state import Repo


EVALUATION_DATE = date(2026, 8, 10)

COMPLETE_LINES = (
    "Medical Certificate",
    "Patient Name: Alyssa Reyes",
    "Diagnosis: Acute Upper Respiratory Tract Infection",
    "Consultation Date: 08/08/2026",
    "Issue Date: 08/09/2026",
    "Absence Start Date: 08/08/2026",
    "Absence End Date: 08/10/2026",
    "Duration Days: 3",
    "Clinician Name: Dr. Sample Physician",
    "Facility Name: Synthetic Care Clinic",
    "License Number: present",
    "Signature: present",
    "Recommendation: present",
)

# Document-content VALUES that must never appear in a persisted or returned
# result. The account holder's id ("emp-alyssa") and safe reason codes
# (e.g. "clinician_name", "patient_name_mismatch") are legitimate metadata and
# are intentionally excluded from this list.
SENSITIVE_TOKENS = (
    "alyssa reyes", "reyes", "sample physician", "synthetic care",
    "08/08/2026", "08/09/2026", "08/10/2026", "private-certificate",
)


def _pdf(lines: tuple[str, ...]) -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer)
    for index, line in enumerate(lines):
        canvas.drawString(72, 720 - index * 18, line)
    canvas.save()
    return buffer.getvalue()


def _png(lines: tuple[str, ...]) -> bytes:
    """Render certificate lines to a clean, high-contrast image for real OCR."""
    image = Image.new("RGB", (1200, 1000), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    for index, line in enumerate(lines):
        draw.text((60, 40 + index * 70), line, fill="black", font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _tesseract_available() -> bool:
    try:
        import pytesseract

        if settings.tesseract_cmd is not None:
            pytesseract.pytesseract.tesseract_cmd = str(settings.tesseract_cmd)
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001 - any failure means OCR cannot run here
        return False


@pytest.fixture
def records():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return load_page_records(root / "handbook" / "dist" / "rag-pages.jsonl")


@pytest.fixture
def service(repo):
    # No agent runner and the real default extractor: the genuine deterministic
    # certificate pipeline, exactly as the demo runs it.
    return MedicalCheckService(repo)


def _assert_private(repo: Repo, outcome) -> None:
    rendered = json.dumps(outcome.model_dump(mode="json")).lower()
    if outcome.validation_id:
        persisted = repo.get_validation_result(outcome.validation_id)
        rendered += json.dumps(persisted).lower()
    for token in SENSITIVE_TOKENS:
        assert token.lower() not in rendered, f"sensitive token leaked into result: {token!r}"


def test_real_pdf_text_extraction_yields_complete_and_private(repo, service, records):
    profile = repo.get_hire_profile("emp-alyssa")
    outcome = service.check(
        _pdf(COMPLETE_LINES),
        filename="private-certificate.pdf",
        evaluation_date=EVALUATION_DATE,
        applicability=resolve_certificate_applicability(records, profile),
        acknowledged=True,
    )
    assert outcome.kind == "validation_result"
    assert outcome.status == ValidationStatus.COMPLETE
    assert outcome.agent_execution.mode == "deterministic"
    _assert_private(repo, outcome)


def test_real_extraction_flags_a_missing_required_field(repo, service, records):
    profile = repo.get_hire_profile("emp-alyssa")
    without_clinician = tuple(l for l in COMPLETE_LINES if not l.startswith("Clinician Name"))
    outcome = service.check(
        _pdf(without_clinician),
        filename="private-certificate.pdf",
        evaluation_date=EVALUATION_DATE,
        applicability=resolve_certificate_applicability(records, profile),
        acknowledged=True,
    )
    assert outcome.kind == "validation_result"
    assert outcome.status == ValidationStatus.INCOMPLETE
    assert "clinician_name" in outcome.missing_codes
    _assert_private(repo, outcome)


def test_alternate_labels_and_placeholder_flag_only_the_truly_missing_field(repo, service, records):
    """A cert with alternate labels and a "[MISSING]" diagnosis placeholder must
    flag diagnosis alone, not the fields that are actually present."""
    profile = repo.get_hire_profile("emp-alyssa")
    lines = (
        "Medical Certificate",
        "Student/Patient Name: Alex Jordan",
        "Date: May 14, 2025",
        "Attending Physician: Dr. Morgan Ellison, MD",
        "Physician License Number: EA-9876543",
        "Diagnosis: [MISSING]",
    )
    outcome = service.check(
        _pdf(lines),
        filename="private-certificate.pdf",
        evaluation_date=EVALUATION_DATE,
        applicability=resolve_certificate_applicability(records, profile),
        acknowledged=True,
    )
    assert outcome.kind == "validation_result"
    assert outcome.status == ValidationStatus.INCOMPLETE
    assert outcome.missing_codes == ["diagnosis"]
    _assert_private(repo, outcome)


def test_computed_applicability_gates_the_flow_before_any_extraction(repo, service, records):
    """A narrowed certificate policy that excludes this Hire stops the pipeline."""
    profile = repo.get_hire_profile("emp-alyssa")
    cert = next(r for r in records if r.page_kind == "policy" and "medical_certificate" in (r.subareas or []))
    narrowed = cert.model_copy(
        update={
            "applicability": {
                "department_keys": ["all"],
                "employment_classifications": ["regular"],
                "role_keys": ["all"],
                "work_sites": ["all"],
            }
        }
    )
    narrowed_records = [narrowed] + [r for r in records if r is not cert]
    applicability = resolve_certificate_applicability(narrowed_records, profile)
    assert applicability == ApplicabilityStatus.DOES_NOT_APPLY

    outcome = service.check(
        _pdf(COMPLETE_LINES),
        filename="private-certificate.pdf",
        evaluation_date=EVALUATION_DATE,
        applicability=applicability,
        acknowledged=True,
    )
    assert outcome.kind == "does_not_apply"
    assert outcome.validation_id is None


@pytest.mark.skipif(not _tesseract_available(), reason="Tesseract OCR binary not available")
def test_real_tesseract_ocr_reads_an_image_certificate_end_to_end(repo, service, records):
    from stai.medical import extract_local_text

    text = extract_local_text(_png(COMPLETE_LINES), "png")
    assert text.strip(), "real OCR returned no text"
    # Clean rendered text should recover the patient's surname.
    assert "Reyes" in text or "reyes" in text.lower()

    profile = repo.get_hire_profile("emp-alyssa")
    outcome = service.check(
        _png(COMPLETE_LINES),
        filename="private-certificate.png",
        evaluation_date=EVALUATION_DATE,
        applicability=resolve_certificate_applicability(records, profile),
        acknowledged=True,
    )
    assert outcome.kind in {
        "validation_result", "retry_required", "needs_human_review",
    }
    _assert_private(repo, outcome)
