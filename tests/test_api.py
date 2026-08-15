import json
from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from reportlab.pdfgen.canvas import Canvas

from stai.api import app, get_repo, get_service
from stai.handbook import build_handbook
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import Repo


class FakeClassifier:
    """Compatibility fake used by the legacy observer tests until Slice 11."""

    def __init__(self, category: str = "on_topic") -> None:
        self.category = category

    def invoke(self, _messages) -> AIMessage:
        return AIMessage(content=json.dumps({"category": self.category}))


@pytest.fixture
def client(tmp_path):
    repo = Repo(tmp_path / "api.db", secret_path=tmp_path / "key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    service = AishaService(repo, records)
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, repo
    app.dependency_overrides.clear()


def headers(key="test-key"):
    return {"Idempotency-Key": key}


def test_only_versioned_health_endpoint_remains(client):
    http, _ = client
    assert http.get("/health").status_code == 404
    assert http.post("/chat", json={}).status_code == 404
    response = http.get("/api/v1/health")
    assert response.status_code == 503
    payload = response.json()
    assert payload["data"]["status"] == "unavailable"
    assert payload["data"]["knowledge_index"] == "degraded"
    assert payload["data"]["agent_model"] == "ready"
    assert payload["data"]["nager"] == "unknown"
    assert payload["meta"]["api_version"] == "v1"


def test_configured_cors_is_not_wildcard(client):
    http, _ = client
    allowed = http.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:8501", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:8501"
    denied = http.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_conversation_create_replay_and_server_owned_history(client):
    http, _ = client
    created = http.post(
        "/api/v1/hires/emp-alyssa/conversations",
        headers=headers(),
        json={"simulated_date": "2026-08-10"},
    )
    assert created.status_code == 201
    conversation = created.json()["data"]
    replay = http.post(
        "/api/v1/hires/emp-alyssa/conversations",
        headers=headers(),
        json={"simulated_date": "2026-08-10"},
    )
    assert replay.status_code == 201 and replay.json()["data"]["id"] == conversation["id"]
    conflict = http.post(
        "/api/v1/hires/emp-alyssa/conversations",
        headers=headers(),
        json={"simulated_date": "2026-08-11"},
    )
    assert conflict.status_code == 409

    turn = http.post(
        f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
        headers=headers("turn-1"),
        json={"message": "What does PAY-001 say?"},
    )
    assert turn.status_code == 200
    assert turn.json()["data"]["type"] == "grounded_answer"
    history = http.get(
        f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages"
    ).json()["data"]
    assert [item["role"] for item in history["items"]] == ["hire", "aisha"]
    assert "history" not in turn.request.content.decode().lower()
    replay_turn = http.post(
        f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
        headers=headers("turn-1"), json={"message": "What does PAY-001 say?"},
    )
    assert replay_turn.status_code == 200
    assert replay_turn.json()["data"] == turn.json()["data"]
    assert len(http.get(f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages").json()["data"]["items"]) == 2


def test_unknown_hire_and_medical_chat_use_safe_errors(client):
    http, _ = client
    unknown = http.post(
        "/api/v1/hires/emp-unknown/conversations",
        headers=headers(),
        json={"simulated_date": "2026-08-10"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "hire_not_found"
    created = http.post(
        "/api/v1/hires/emp-alyssa/conversations",
        headers=headers("c2"), json={"simulated_date": "2026-08-10"},
    ).json()["data"]
    blocked = http.post(
        f"/api/v1/hires/emp-alyssa/conversations/{created['id']}/messages",
        headers=headers("medical-chat"),
        json={"message": "Here is my medical certificate diagnosis"},
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "medical_content_requires_certificate_check"


def test_escalation_offer_to_consent_case(client):
    http, _ = client
    conversation = http.post(
        "/api/v1/hires/emp-alyssa/conversations", headers=headers("c3"),
        json={"simulated_date": "2026-08-10"},
    ).json()["data"]
    offer = http.post(
        f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
        headers=headers("offer"), json={"message": "Where is the official payroll route?"},
    ).json()["data"]
    assert offer["type"] == "escalation_offer"
    consent = http.post(
        f"/api/v1/hires/emp-alyssa/escalation-offers/{offer['offer_id']}/consent",
        headers=headers("consent"), json={"expected_version": 1},
    )
    assert consent.status_code == 201
    assert consent.json()["data"]["status"] == "open"
    case_id = consent.json()["data"]["case_id"]
    assert http.get(f"/api/v1/hires/emp-alyssa/escalation-cases/{case_id}").status_code == 200
    closed = http.post(
        f"/api/v1/hr/escalation-cases/{case_id}/close", headers=headers("close"),
        json={"expected_version": 1, "hr_user": "hr-demo"},
    )
    assert closed.status_code == 200 and closed.json()["data"]["status"] == "closed"


def test_case_thread_api_mirrors_parent_and_separates_hr_internal_notes(client):
    http, _repo = client
    conversation = http.post(
        "/api/v1/hires/emp-alyssa/conversations",
        headers=headers("thread-conversation"),
        json={"simulated_date": "2026-08-10"},
    ).json()["data"]
    offer = http.post(
        f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
        headers=headers("thread-offer"),
        json={"message": "Where is the official payroll route?"},
    ).json()["data"]
    case = http.post(
        f"/api/v1/hires/emp-alyssa/escalation-offers/{offer['offer_id']}/consent",
        headers=headers("thread-consent"),
        json={"expected_version": 1},
    ).json()["data"]
    case_id = case["case_id"]

    parent_reply = http.post(
        f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
        headers=headers("thread-parent-reply"),
        json={"message": "Where is the official payroll route?"},
    )
    assert parent_reply.status_code == 200
    hire_thread = http.get(
        f"/api/v1/hires/emp-alyssa/escalation-cases/{case_id}/messages"
    ).json()["data"]
    assert hire_thread["messages"][-2]["text"].startswith("Where is")

    version = hire_thread["case"]["resource_version"]
    internal = http.post(
        f"/api/v1/hr/escalation-cases/{case_id}/messages",
        headers=headers("thread-internal"),
        json={"expected_version": version, "message": "Internal triage", "internal": True},
    )
    assert internal.status_code == 201
    hr_thread = internal.json()["data"]
    assert hr_thread["messages"][-1]["visibility"] == "hr_internal"
    hire_after = http.get(
        f"/api/v1/hires/emp-alyssa/escalation-cases/{case_id}/messages"
    ).json()["data"]
    assert "Internal triage" not in {item["text"] for item in hire_after["messages"]}

    rejected_direct = http.post(
        f"/api/v1/hr/escalation-cases/{case_id}/messages",
        headers=headers("thread-direct-rejected"),
        json={
            "expected_version": hr_thread["case"]["resource_version"],
            "message": "Direct HR reply before separate consent.",
            "internal": False,
        },
    )
    assert rejected_direct.status_code == 409

    requested = http.post(
        f"/api/v1/hr/escalation-cases/{case_id}/information-requests",
        headers=headers("thread-information-request"),
        json={
            "expected_version": hr_thread["case"]["resource_version"],
            "question": "Which pay period is affected?",
            "hr_user": "hr-demo",
        },
    )
    assert requested.status_code == 201
    requested_thread = requested.json()["data"]
    assert requested_thread["case"]["workflow_state"] == "waiting_for_hire"
    assert requested_thread["messages"][-1]["actor_role"] == "aisha"
    assert requested_thread["information_requests"][-1]["status"] == "pending"

    answered = http.post(
        f"/api/v1/hires/emp-alyssa/escalation-cases/{case_id}/messages",
        headers=headers("thread-information-answer"),
        json={
            "expected_version": requested_thread["case"]["resource_version"],
            "message": "The 1–15 August pay period.",
        },
    )
    assert answered.status_code == 201
    assert answered.json()["data"]["information_requests"][-1]["status"] == "answered"


def test_direct_case_conversation_requires_hr_offer_and_hire_consent(client):
    http, _repo = client
    conversation = http.post(
        "/api/v1/hires/emp-alyssa/conversations", headers=headers("direct-c"),
        json={"simulated_date": "2026-08-10"},
    ).json()["data"]
    offer = http.post(
        f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
        headers=headers("direct-policy-offer"),
        json={"message": "Where is the official payroll route?"},
    ).json()["data"]
    case = http.post(
        f"/api/v1/hires/emp-alyssa/escalation-offers/{offer['offer_id']}/consent",
        headers=headers("direct-case-consent"), json={"expected_version": offer["version"]},
    ).json()["data"]
    case_id = case["case_id"]
    offered = http.post(
        f"/api/v1/hr/escalation-cases/{case_id}/direct-conversation/offer",
        headers=headers("direct-offer"),
        json={"expected_version": case["resource_version"], "hr_user": "hr-demo"},
    )
    assert offered.status_code == 200
    offered_thread = offered.json()["data"]
    assert offered_thread["interaction_mode"]["mode"] == "direct_offered"
    consented = http.post(
        f"/api/v1/hires/emp-alyssa/escalation-cases/{case_id}/direct-conversation/consent",
        headers=headers("direct-hire-consent"),
        json={"expected_version": offered_thread["case"]["resource_version"]},
    )
    assert consented.status_code == 200
    consented_thread = consented.json()["data"]
    assert consented_thread["interaction_mode"]["mode"] == "direct_consented"
    direct = http.post(
        f"/api/v1/hr/escalation-cases/{case_id}/messages",
        headers=headers("direct-message"),
        json={
            "expected_version": consented_thread["case"]["resource_version"],
            "message": "I can now speak with you directly.",
            "internal": False,
        },
    )
    assert direct.status_code == 201
    assert direct.json()["data"]["messages"][-1]["actor_role"] == "hr"


def test_structured_resolution_thread_memory_and_reviewed_reuse_api(client):
    http, _repo = client
    conversation = http.post(
        "/api/v1/hires/emp-alyssa/conversations",
        headers=headers("clarification-conversation"),
        json={"simulated_date": "2026-08-10"},
    ).json()["data"]
    offer = http.post(
        f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
        headers=headers("clarification-offer"),
        json={"message": "Where is the official payroll route?"},
    ).json()["data"]
    case = http.post(
        f"/api/v1/hires/emp-alyssa/escalation-offers/{offer['offer_id']}/consent",
        headers=headers("clarification-consent"),
        json={"expected_version": offer["version"]},
    ).json()["data"]
    case_id = case["case_id"]
    closed = http.post(
        f"/api/v1/hr/escalation-cases/{case_id}/close",
        headers=headers("clarification-close"),
        json={
            "expected_version": case["resource_version"],
            "hr_user": "hr-demo",
            "resolution_summary": "Use the Payroll Support form in the onboarding portal.",
            "resolution_type": "policy_clarification",
            "resolution_scope": "organization",
            "propose_for_reuse": True,
        },
    )
    assert closed.status_code == 200
    thread = http.get(
        f"/api/v1/hires/emp-alyssa/escalation-cases/{case_id}/messages"
    ).json()["data"]
    assert thread["resolution"]["reuse_status"] == "pending_review"

    follow_up = http.post(
        f"/api/v1/hires/emp-alyssa/escalation-cases/{case_id}/messages",
        headers=headers("clarification-follow-up"),
        json={
            "expected_version": thread["case"]["resource_version"],
            "message": "What does that mean for me?",
        },
    )
    assert follow_up.status_code == 201
    assert "Case Resolution Memory" in follow_up.json()["data"]["messages"][-1]["text"]

    reviewed = http.post(
        f"/api/v1/hr/escalation-cases/{case_id}/clarification-review/approve",
        headers=headers("clarification-review"),
        json={
            "expected_version": thread["resolution"]["resource_version"],
            "hr_user": "policy-owner-demo",
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["reuse_status"] == "approved"

    future = http.post(
        "/api/v1/hires/emp-alyssa/conversations",
        headers=headers("clarification-future-conversation"),
        json={"simulated_date": "2026-08-10"},
    ).json()["data"]
    reused = http.post(
        f"/api/v1/hires/emp-alyssa/conversations/{future['id']}/messages",
        headers=headers("clarification-reused"),
        json={"message": "Where is the official payroll route?"},
    )
    assert reused.status_code == 200
    payload = reused.json()["data"]
    assert payload["type"] == "grounded_answer"
    assert payload["clarifications"][0]["clarification_id"] == reviewed.json()["data"]["resolution_id"]


def test_production_payroll_transcript_has_identical_api_semantics(client):
    http, repo = client
    conversation = http.post(
        "/api/v1/hires/emp-alyssa/conversations",
        headers=headers("incident-conversation"),
        json={"simulated_date": "2026-08-10"},
    ).json()["data"]
    prompts = [
        "Whats my payroll",
        "Well then how do i do the onboard",
        "How to i put my payroll details",
        "I need help in this",
        "route it please",
        "how does payroll work",
    ]
    results = []
    for index, prompt in enumerate(prompts):
        response = http.post(
            f"/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
            headers=headers(f"incident-{index}"),
            json={"message": prompt},
        )
        assert response.status_code == 200
        results.append(response.json()["data"])

    assert [item["type"] for item in results] == [
        "grounded_answer", "escalation_offer", "escalation_offer",
        "escalation_offer", "escalation_confirmation", "grounded_answer",
    ]
    assert all(
        citation["policy_id"].startswith("PAY-")
        for item in results
        for citation in item.get("citations", [])
    )
    assert results[-1]["citations"][0]["policy_id"] == "PAY-001"
    assert repo.list_escalation_cases()[0]["topic"] == "payroll"


def test_attribute_request_hr_approval_uses_versions(client):
    http, _ = client
    request = http.post(
        "/api/v1/hires/emp-alyssa/attribute-change-requests",
        headers=headers("attr"),
        json={"attribute_name": "work_site", "proposed_value": "remote", "consent": True},
    )
    assert request.status_code == 201
    item = request.json()["data"]
    approved = http.post(
        f"/api/v1/hr/attribute-change-requests/{item['request_id']}/approve",
        headers=headers("approve"),
        json={"expected_version": 1, "expected_profile_revision": 1, "hr_user": "hr-demo"},
    )
    assert approved.status_code == 200
    profile = http.get("/api/v1/hires/emp-alyssa/profile").json()["data"]
    assert profile["work_site"] == "remote" and profile["revision"] == 2
    assert http.get(f"/api/v1/hr/attribute-change-requests/{item['request_id']}").status_code == 200


def synthetic_certificate(*, two_digit_issue=False) -> bytes:
    buffer = BytesIO(); canvas = Canvas(buffer)
    lines = [
        "Patient Name: Alyssa Reyes", "Consultation Date: 08/08/2026",
        f"Issue Date: {'08/09/26' if two_digit_issue else '08/09/2026'}",
        "Absence Start Date: 08/08/2026", "Absence End Date: 08/10/2026",
        "Duration Days: 3", "Clinician Name: Dr. Sample Physician",
        "Facility Name: Synthetic Care Clinic", "License Number: DEMO-123",
        "Signature: Present", "Recommendation: Rest",
    ]
    for index, line in enumerate(lines): canvas.drawString(72, 740 - index * 20, line)
    canvas.save(); return buffer.getvalue()


def test_certificate_result_history_share_revoke_delete_and_idempotency(client):
    http, _ = client; content = synthetic_certificate()
    response = http.post(
        "/api/v1/hires/emp-alyssa/certificate-checks", headers=headers("cert-1"),
        data={"evaluation_date": "2026-08-10", "acknowledged": "true"},
        files={"file": ("synthetic.pdf", content, "application/pdf")},
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["kind"] == "validation_result" and result["status"] == "complete"
    assert result["agent_execution"]["mode"] in {
        "react", "deterministic", "deterministic_degraded"
    }
    assert result["agent_execution"]["actions"][-1] == "persist_safe_result"
    replay = http.post(
        "/api/v1/hires/emp-alyssa/certificate-checks", headers=headers("cert-1"),
        data={"evaluation_date": "2026-08-10", "acknowledged": "true"},
        files={"file": ("synthetic.pdf", content, "application/pdf")},
    )
    assert replay.json()["data"] == result
    validation_id = result["validation_id"]
    assert http.get(f"/api/v1/hires/emp-alyssa/validation-results/{validation_id}").status_code == 200
    assert http.get("/api/v1/hr/validation-results").json()["data"]["items"] == []
    shared = http.post(
        f"/api/v1/hires/emp-alyssa/validation-results/{validation_id}/share",
        headers=headers("share"), json={"expected_version": 1},
    )
    assert shared.json()["data"]["share_state"] == "shared"
    assert http.get(f"/api/v1/hr/validation-results/{validation_id}").status_code == 200
    revoked = http.post(
        f"/api/v1/hires/emp-alyssa/validation-results/{validation_id}/revoke",
        headers=headers("revoke"), json={"expected_version": 2},
    )
    assert revoked.json()["data"]["share_state"] == "private"
    deleted = http.request(
        "DELETE", f"/api/v1/hires/emp-alyssa/validation-results/{validation_id}",
        headers=headers("delete"), json={"expected_version": 3},
    )
    assert deleted.json()["data"] == {"deleted": True}


def test_certificate_retry_uses_one_replacement_and_creates_no_first_result(client):
    http, repo = client
    first = http.post(
        "/api/v1/hires/emp-alyssa/certificate-checks", headers=headers("retry-first"),
        data={"evaluation_date": "2026-08-10", "acknowledged": "true"},
        files={"file": ("synthetic.pdf", synthetic_certificate(two_digit_issue=True), "application/pdf")},
    )
    assert first.json()["data"]["kind"] == "retry_required"
    assert repo.count_validation_results() == 0
    token = first.json()["data"]["retry_token"]
    second = http.post(
        "/api/v1/hires/emp-alyssa/certificate-checks/retry", headers=headers("retry-second"),
        data={"evaluation_date": "2026-08-10", "retry_token": token},
        files={"file": ("replacement.pdf", synthetic_certificate(), "application/pdf")},
    )
    assert second.json()["data"]["kind"] == "validation_result"
    assert second.json()["data"]["attempt_count"] == 2


def test_conversation_cursor_pagination_is_bounded(client):
    http, _ = client
    for index in range(3):
        http.post(
            "/api/v1/hires/emp-alyssa/conversations", headers=headers(f"page-{index}"),
            json={"simulated_date": f"2026-08-{10 + index:02d}"},
        )
    first = http.get("/api/v1/hires/emp-alyssa/conversations?limit=2").json()["data"]
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = http.get(
        "/api/v1/hires/emp-alyssa/conversations",
        params={"limit": 2, "cursor": first["next_cursor"]},
    ).json()["data"]
    assert len(second["items"]) == 1
    assert http.get("/api/v1/hires/emp-alyssa/conversations?limit=101").status_code == 422
