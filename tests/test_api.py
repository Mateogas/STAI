import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

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
        headers=headers("offer"), json={"message": "Please connect me with a human about PAY-001"},
    ).json()["data"]
    assert offer["type"] == "escalation_offer"
    consent = http.post(
        f"/api/v1/hires/emp-alyssa/escalation-offers/{offer['offer_id']}/consent",
        headers=headers("consent"), json={"expected_version": 1},
    )
    assert consent.status_code == 201
    assert consent.json()["data"]["status"] == "open"


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
