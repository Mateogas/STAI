from datetime import date
from pathlib import Path

import pytest

from stai.handbook import build_handbook
from stai.models import ApplicabilityStatus
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import MedicalContentRejected, Repo


def make_service(tmp_path: Path) -> AishaService:
    repo = Repo(tmp_path / "db.sqlite", secret_path=tmp_path / "install.key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    return AishaService(repo, records)


def test_conversation_memory_is_server_owned_and_survives_restart(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    response = service.send_message(conversation["id"], "What does PAY-001 say?")
    assert response.type == "grounded_answer"
    restarted = AishaService(service.repo, service.records)
    messages = restarted.list_messages(conversation["id"])
    assert [message["role"] for message in messages] == ["hire", "aisha"]
    assert "PAY-001" in messages[1]["text"]


def test_certificate_content_never_enters_conversation_memory(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    with pytest.raises(MedicalContentRejected):
        service.send_message(conversation["id"], "My medical certificate diagnosis says...")
    assert service.list_messages(conversation["id"]) == []


def test_escalation_offer_requires_separate_consent(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    offer = service.send_message(conversation["id"], "Where is the official payroll route?")
    assert offer.type == "escalation_offer"
    assert service.repo.list_escalation_cases() == []
    case = service.consent_escalation(offer.offer_id, expected_version=1)
    assert case["status"] == "open"
    assert case["approved_summary"] == offer.proposed_summary
    assert "human about" not in case["approved_summary"]


def test_attribute_change_request_is_one_attribute_and_hr_confirmed(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = service.request_attribute_change(
        "emp-alyssa", "work_site", "remote", consent=True
    )
    assert request["status"] == "pending"
    updated = service.resolve_attribute_request(
        request["request_id"], approve=True, expected_version=1,
        expected_profile_revision=1, hr_user="hr-demo",
    )
    assert updated["status"] == "approved"
    assert service.repo.get_hire_profile("emp-alyssa").work_site == "remote"
    assert service.repo.get_hire_profile("emp-alyssa").revision == 2


def test_result_share_revoke_delete_lifecycle_is_result_only(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = service.repo.create_validation_result(
        status="incomplete",
        missing_codes=["facility_name"],
        inconsistency_codes=[],
        warning_codes=[],
        review_codes=[],
        evaluation_date=date(2026, 8, 10),
        fingerprint="private-hmac",
    )
    assert service.repo.list_shared_validation_results() == []
    shared = service.share_validation_result(result["validation_id"], expected_version=1)
    assert shared["share_state"] == "shared"
    public_hr = service.repo.list_shared_validation_results()
    assert public_hr[0]["codes"] == [{"family": "missing", "code": "facility_name"}]
    assert "document_fingerprint" not in public_hr[0]
    revoked = service.revoke_validation_result(result["validation_id"], expected_version=2)
    assert revoked["share_state"] == "private"
    service.delete_validation_result(result["validation_id"], expected_version=3)
    assert service.repo.count_validation_results() == 0
