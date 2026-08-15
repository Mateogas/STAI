"""CPU-only Certificate Agent orchestration and privacy contracts."""

import json
from datetime import date
from io import BytesIO

from reportlab.pdfgen.canvas import Canvas

from stai.certificate_agent import CertificateAgentRun, build_certificate_tools
from stai.medical import CertificateFields, MedicalCheckService, validate_certificate_fields
from stai.models import ApplicabilityStatus, ValidationStatus
from stai.state import Repo


def synthetic_certificate() -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer)
    for index, line in enumerate(
        (
            "Patient Name: Alyssa Reyes",
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
    ):
        canvas.drawString(72, 720 - index * 18, line)
    canvas.save()
    return buffer.getvalue()


def complete_fields() -> CertificateFields:
    return CertificateFields(
        patient_name="Alyssa Reyes",
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
        diagnosis_present=True,
    )


def test_certificate_tools_expose_only_safe_typed_results() -> None:
    validation = validate_certificate_fields(complete_fields(), "Alyssa Reyes", date(2026, 8, 10))
    tools, capture = build_certificate_tools(lambda: validation)

    requirements = json.loads(tools[0].invoke({}))
    result = json.loads(tools[1].invoke({}))

    assert requirements["policy_id"] == "HRP-004"
    assert result["status"] == "complete"
    assert capture.actions == ["confirm_certificate_policy", "run_local_ocr_validation"]
    rendered = json.dumps(result).lower()
    for forbidden in ("alyssa", "patient_name", "consultation_date", "ocr_text", "filename"):
        assert forbidden not in rendered


class ToolCallingRunner:
    def __call__(self, analyze):
        validation = analyze()
        return CertificateAgentRun(
            validation=validation,
            actions=["confirm_certificate_policy", "run_local_ocr_validation"],
        )


def test_certificate_agent_trace_is_persisted_without_document_content(tmp_path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    service = MedicalCheckService(
        repo,
        extractor=lambda _data, _kind: complete_fields(),
        agent_runner=ToolCallingRunner(),
    )

    outcome = service.check(
        synthetic_certificate(),
        filename="private-certificate.pdf",
        evaluation_date=date(2026, 8, 10),
        applicability=ApplicabilityStatus.APPLIES,
        acknowledged=True,
    )

    assert outcome.status == ValidationStatus.COMPLETE
    assert outcome.agent_execution.mode == "react"
    assert outcome.agent_execution.actions == [
        "confirm_certificate_policy",
        "run_local_ocr_validation",
        "validate_certificate_result",
        "persist_safe_result",
    ]
    persisted = repo.get_validation_result(outcome.validation_id)
    assert persisted["agent_execution"] == outcome.agent_execution.model_dump(mode="json")
    rendered = json.dumps(persisted).lower()
    for forbidden in ("private-certificate", "alyssa reyes", "patient_name", "ocr_text"):
        assert forbidden not in rendered


def test_invalid_agent_run_degrades_to_deterministic_validation(tmp_path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    service = MedicalCheckService(
        repo,
        extractor=lambda _data, _kind: complete_fields(),
        agent_runner=lambda _analyze: None,
    )

    outcome = service.check(
        synthetic_certificate(),
        filename="certificate.pdf",
        evaluation_date=date(2026, 8, 10),
        applicability=ApplicabilityStatus.APPLIES,
        acknowledged=True,
    )

    assert outcome.status == ValidationStatus.COMPLETE
    assert outcome.agent_execution.mode == "deterministic_degraded"
    assert outcome.agent_execution.actions[-2:] == [
        "validate_certificate_result",
        "persist_safe_result",
    ]
