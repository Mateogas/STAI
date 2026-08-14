from datetime import date
from pathlib import Path

import pytest

from stai.cases import CaseActor, CaseWorkflow
from stai.handbook import build_handbook
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import Repo


def setup_case(tmp_path: Path):
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    service = AishaService(repo, records)
    conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    service.send_message(conversation["id"], "How do I change my payroll details?")
    offer = service.send_message(conversation["id"], "Connect me with payroll support")
    confirmation = service.consent_escalation_from_conversation(
        conversation["id"], offer.offer_id, expected_version=offer.version,
    )
    return repo, service, conversation, confirmation.case_id


def test_case_thread_backfills_parent_and_mirrors_future_messages(tmp_path: Path) -> None:
    _repo, service, conversation, case_id = setup_case(tmp_path)
    initial = service.get_case_thread(case_id)
    assert [item["actor_role"] for item in initial["messages"]] == [
        "hire", "aisha", "hire", "aisha", "hire", "aisha",
    ]
    assert initial["case"]["parent_conversation_id"] == conversation["id"]
    assert initial["case"]["sharing_active"] == 1

    service.send_message(conversation["id"], "My concern is the official payroll route")
    mirrored = service.get_case_thread(case_id)
    assert [item["actor_role"] for item in mirrored["messages"][-2:]] == ["hire", "aisha"]
    assert mirrored["messages"][-2]["text"].startswith("My concern")
    assert mirrored["case"]["workflow_state"] == "waiting_for_hr"


def test_agent_mediates_information_request_internal_note_and_resolution(tmp_path: Path) -> None:
    _repo, service, conversation, case_id = setup_case(tmp_path)
    workflow = service.case_workflow
    hr = CaseActor.hr()
    hire = CaseActor.hire()

    case = workflow.get_case(case_id, hr)
    workflow.request_information(
        case_id, hr, "Which payroll record needs correction?",
        expected_version=case["resource_version"],
    )
    assert workflow.list_notifications(hire, unread_only=True)[0]["kind"] == "case_reply"
    hire_thread = workflow.get_thread(case_id, hire)
    assert hire_thread["case"]["workflow_state"] == "waiting_for_hire"
    assert hire_thread["messages"][-1]["actor_role"] == "aisha"
    assert "AISHA needs one detail" in hire_thread["messages"][-1]["text"]
    assert hire_thread["information_requests"][-1]["status"] == "pending"

    workflow.answer_information_request(
        case_id, hire, "The first pay period after my start date.",
        expected_version=hire_thread["case"]["resource_version"],
    )
    answered = workflow.get_thread(case_id, hr)
    assert answered["case"]["workflow_state"] == "waiting_for_hr"
    assert answered["information_requests"][-1]["status"] == "answered"
    assert answered["information_requests"][-1]["hire_response"].startswith("The first")

    workflow.post_message(
        case_id, hr, "Internal triage note",
        expected_version=answered["case"]["resource_version"], internal=True,
    )
    assert "Internal triage note" not in {
        item["text"] for item in workflow.get_thread(case_id, hire)["messages"]
    }
    assert "Internal triage note" in {
        item["text"] for item in workflow.get_thread(case_id, hr)["messages"]
    }

    current = workflow.get_case(case_id, hr)
    resolved = workflow.resolve(
        case_id, hr, "Payroll Support provided the official correction route.",
        expected_version=current["resource_version"],
    )
    assert resolved["status"] == "closed"
    assert resolved["sharing_active"] == 0
    count = len(workflow.get_thread(case_id, hire)["messages"])
    service.send_message(conversation["id"], "This parent message is private again")
    assert len(workflow.get_thread(case_id, hire)["messages"]) == count
    assert workflow.list_notifications(hire, unread_only=True)[0]["kind"] == "case_resolved"


def test_case_permissions_and_versions_fail_closed(tmp_path: Path) -> None:
    _repo, service, _conversation, case_id = setup_case(tmp_path)
    workflow = CaseWorkflow(service.repo)
    with pytest.raises(PermissionError):
        workflow.get_case(case_id, CaseActor.hire("emp-other"))
    current = workflow.get_case(case_id, CaseActor.hr())
    with pytest.raises(ValueError, match="stale"):
        workflow.post_message(
            case_id, CaseActor.hr(), "A reply",
            expected_version=current["resource_version"] + 1,
        )
    with pytest.raises(PermissionError, match="Case Information Request"):
        workflow.post_message(
            case_id, CaseActor.hr(), "A direct reply",
            expected_version=current["resource_version"],
        )


def test_direct_human_conversation_requires_a_separate_hire_consent(tmp_path: Path) -> None:
    _repo, service, _conversation, case_id = setup_case(tmp_path)
    workflow = service.case_workflow
    hr = CaseActor.hr()
    hire = CaseActor.hire()
    case = workflow.get_case(case_id, hr)
    workflow.offer_direct_conversation(case_id, hr, expected_version=case["resource_version"])
    offered = workflow.get_thread(case_id, hire)
    assert offered["interaction_mode"]["mode"] == "direct_offered"
    with pytest.raises(PermissionError):
        workflow.post_message(
            case_id, hr, "Hello directly",
            expected_version=offered["case"]["resource_version"],
        )
    workflow.consent_direct_conversation(
        case_id, hire, expected_version=offered["case"]["resource_version"]
    )
    consented = workflow.get_thread(case_id, hr)
    assert consented["interaction_mode"]["mode"] == "direct_consented"
    workflow.post_message(
        case_id, hr, "Hello directly",
        expected_version=consented["case"]["resource_version"],
    )
