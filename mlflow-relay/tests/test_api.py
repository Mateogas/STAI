"""Relay allowlist, authentication, partial delivery, and idempotency tests."""

from __future__ import annotations

import uuid

import mlflow
import pytest
from fastapi.testclient import TestClient
from mlflow.tracking import MlflowClient


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    monkeypatch.setenv("RELAY_MLFLOW_TRACKING_URI", tracking_uri)
    monkeypatch.delenv("RELAY_SHARED_SECRET", raising=False)
    from relay import api, config
    config.settings.mlflow_tracking_uri = tracking_uri
    config.settings.shared_secret = None
    mlflow.set_tracking_uri(tracking_uri)
    api.client = MlflowClient()
    return TestClient(api.app)


def _run(event_id=None):
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "event_kind": "dialogue",
        "run_name": "dialogue-20260810T000000Z-deadbeef",
        "start_time_ms": 1786320000000,
        "end_time_ms": 1786320000010,
        "tags": {"event_kind": "dialogue", "route": "api", "outcome": "grounded_answer"},
        "metrics": {"duration_ms": 10.0, "citation_count": 0.0},
    }


def test_health(app_client):
    assert app_client.get("/health").json()["mlflow_reachable"] is True


def test_event_id_is_idempotent_after_response_loss(app_client):
    payload = _run()
    first = app_client.post("/log-batch", json={"runs": [payload]})
    second = app_client.post("/log-batch", json={"runs": [payload]})
    assert first.json()["accepted_event_ids"] == [payload["event_id"]]
    assert second.json()["already_present_event_ids"] == [payload["event_id"]]
    from relay.api import client
    exp = client.get_experiment_by_name("aisha-chat-turns")
    assert len(client.search_runs([exp.experiment_id])) == 1


def test_experiment_is_closed_mapping_not_input(app_client):
    for kind, experiment in [
        ("certificate_check", "aisha-certificate-checks"),
        ("system_operation", "aisha-system-operations"),
        ("benchmark_case", "aisha-benchmark"),
    ]:
        payload = _run(); payload["event_kind"] = kind; payload["tags"]["event_kind"] = kind
        response = app_client.post("/log-batch", json={"runs": [payload]})
        assert response.status_code == 200
        from relay.api import client
        assert client.get_experiment_by_name(experiment) is not None


def test_relay_rejects_unknown_tags_metrics_and_arbitrary_experiment(app_client):
    payload = _run(); payload["tags"]["employee_id"] = "emp-alyssa"
    assert app_client.post("/log-batch", json={"runs": [payload]}).status_code == 422
    payload = _run(); payload["metrics"]["raw_score"] = 0.8
    assert app_client.post("/log-batch", json={"runs": [payload]}).status_code == 422
    payload = _run(); payload["experiment_name"] = "attacker-selected"
    assert app_client.post("/log-batch", json={"runs": [payload]}).status_code == 422


def test_batch_bound_and_partial_downstream_failure(app_client, monkeypatch):
    assert app_client.post("/log-batch", json={"runs": [_run() for _ in range(101)]}).status_code == 422
    from relay import api
    original = api._log_one_run
    bad_id = str(uuid.uuid4())
    def sometimes(payload):
        if payload.event_id == bad_id:
            raise RuntimeError("downstream")
        return original(payload)
    monkeypatch.setattr(api, "_log_one_run", sometimes)
    good = _run(); bad = _run(bad_id)
    response = app_client.post("/log-batch", json={"runs": [good, bad]})
    assert response.status_code == 200
    assert response.json()["accepted_event_ids"] == [good["event_id"]]
    assert response.json()["retryable_event_ids"] == [bad_id]


def test_authentication(app_client):
    from pydantic import SecretStr
    from relay import config
    config.settings.shared_secret = SecretStr("dev-secret")
    try:
        assert app_client.post("/log-batch", json={"runs": [_run()]}).status_code == 401
        assert app_client.post(
            "/log-batch", json={"runs": [_run()]}, headers={"Authorization": "Bearer dev-secret"}
        ).status_code == 200
    finally:
        config.settings.shared_secret = None
