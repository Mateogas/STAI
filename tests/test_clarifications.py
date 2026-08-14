from datetime import date
from pathlib import Path

from stai.handbook import build_handbook
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import Repo


def setup(tmp_path: Path):
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    service = AishaService(repo, records)
    conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    return repo, service, conversation


def create_route_case(service: AishaService, conversation: dict) -> str:
    offer = service.send_message(conversation["id"], "Where is the official payroll route?")
    assert offer.type == "escalation_offer"
    confirmation = service.consent_escalation_from_conversation(
        conversation["id"], offer.offer_id, expected_version=offer.version,
    )
    return confirmation.case_id


def test_device_social_media_is_grounded_and_bare_human_request_does_not_offer_hr(tmp_path: Path) -> None:
    repo, service, conversation = setup(tmp_path)

    absent = service.send_message(
        conversation["id"],
        "What is the policy for personal social media on work laptops?",
    )
    assert absent.type == "grounded_answer"
    assert absent.citations[0].policy_id == "ACC-004"
    assert repo.get_pending_escalation_offer_for_conversation(conversation["id"]) is None

    request = service.send_message(conversation["id"], "Connect me with HR")
    assert request.type in {"abstention", "clarification_request"}
    assert repo.get_pending_escalation_offer_for_conversation(conversation["id"]) is None


def test_resolved_thread_uses_case_resolution_memory(tmp_path: Path) -> None:
    _repo, service, conversation = setup(tmp_path)
    case_id = create_route_case(service, conversation)
    case = service.get_case_thread(case_id, hr=True)["case"]
    service.resolve_case(
        case_id,
        "Use the fictional Payroll Support form in the onboarding portal.",
        expected_version=case["resource_version"],
        resolution_type="case_exception",
        resolution_scope="case_only",
    )
    resolved = service.get_case_thread(case_id)
    assert resolved["resolution"]["reuse_status"] == "thread_only"

    answered = service.post_case_message(
        case_id,
        "What does that mean for me?",
        expected_version=resolved["case"]["resource_version"],
    )
    assert answered["messages"][-2]["actor_role"] == "hire"
    assert answered["messages"][-1]["actor_role"] == "aisha"
    assert "Payroll Support form" in answered["messages"][-1]["text"]
    assert "Case Resolution Memory" in answered["messages"][-1]["text"]


def test_reviewed_clarification_supplements_future_policy_answers(tmp_path: Path) -> None:
    _repo, service, conversation = setup(tmp_path)
    case_id = create_route_case(service, conversation)
    case = service.get_case_thread(case_id, hr=True)["case"]
    service.resolve_case(
        case_id,
        "The fictional official payroll route is the Payroll Support form in the onboarding portal.",
        expected_version=case["resource_version"],
        resolution_type="policy_clarification",
        resolution_scope="organization",
        propose_for_reuse=True,
    )
    pending = service.clarification_workflow.get_resolution(case_id)
    assert pending["reuse_status"] == "pending_review"
    approved = service.review_case_clarification(
        case_id,
        approve=True,
        expected_version=pending["resource_version"],
    )
    assert approved["reuse_status"] == "approved"

    future = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    answer = service.send_message(future["id"], "Where is the official payroll route?")
    assert answer.type == "grounded_answer"
    assert "Reviewed HR clarification" in answer.text
    assert "Payroll Support form" in answer.text
    assert answer.clarifications[0].clarification_id == approved["resolution_id"]
    assert service.repo.get_pending_escalation_offer_for_conversation(future["id"]) is None


def test_case_exception_never_becomes_global_and_open_case_is_deduplicated(tmp_path: Path) -> None:
    _repo, service, conversation = setup(tmp_path)
    case_id = create_route_case(service, conversation)

    duplicate = service.send_message(conversation["id"], "Where is that payroll route?")
    assert duplicate.type == "escalation_confirmation"
    assert duplicate.case_id == case_id
    assert len(service.list_cases(parent_conversation_id=conversation["id"])) == 1

    current = service.get_case_thread(case_id, hr=True)["case"]
    service.resolve_case(
        case_id,
        "A one-time exception was approved for this case.",
        expected_version=current["resource_version"],
        resolution_type="case_exception",
        resolution_scope="case_only",
    )
    future = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    result = service.send_message(future["id"], "Where is the official payroll route?")
    assert result.type == "escalation_offer"


def test_policy_amendment_candidate_waits_for_handbook_revision(tmp_path: Path) -> None:
    _repo, service, conversation = setup(tmp_path)
    case_id = create_route_case(service, conversation)
    case = service.get_case_thread(case_id, hr=True)["case"]
    service.resolve_case(
        case_id,
        "The official rule may need a revised route.",
        expected_version=case["resource_version"],
        resolution_type="policy_amendment_candidate",
        resolution_scope="organization",
    )
    resolution = service.clarification_workflow.get_resolution(case_id)
    assert resolution["reuse_status"] == "pending_handbook"
