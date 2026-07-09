"""Relay API tests: file:// tracking URI, no real mlflow server needed."""

from __future__ import annotations

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


RUN_PAYLOAD = {
    "experiment_name": "smoke-test",
    "run_name": "manual-run",
    "start_time_ms": 1751000000000,
    "end_time_ms": 1751000001500,
    "tags": {"route": "api", "employee_id": "emp-alyssa"},
    "metrics": {"latency_ms": 1500.0, "refused": 0.0},
}


def test_health(app_client):
    resp = app_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["mlflow_reachable"] is True


def test_log_batch_creates_run(app_client):
    resp = app_client.post("/log-batch", json={"runs": [RUN_PAYLOAD]})
    assert resp.status_code == 200
    assert resp.json()["created"] == 1

    from relay.api import client

    experiment = client.get_experiment_by_name("smoke-test")
    assert experiment is not None
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 1
    run = runs[0]
    assert run.data.tags["route"] == "api"
    assert run.data.metrics["latency_ms"] == 1500.0
    assert run.info.status == "FINISHED"


def test_log_batch_multiple_runs_same_experiment(app_client):
    resp = app_client.post("/log-batch", json={"runs": [RUN_PAYLOAD, RUN_PAYLOAD]})
    assert resp.status_code == 200
    assert resp.json()["created"] == 2

    from relay.api import client

    experiment = client.get_experiment_by_name("smoke-test")
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 2


def test_log_batch_requires_auth_when_secret_configured(tmp_path, monkeypatch):
    tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    monkeypatch.setenv("RELAY_MLFLOW_TRACKING_URI", tracking_uri)
    from relay import api, config

    config.settings.mlflow_tracking_uri = tracking_uri
    from pydantic import SecretStr

    config.settings.shared_secret = SecretStr("dev-secret")
    mlflow.set_tracking_uri(tracking_uri)
    api.client = MlflowClient()
    client = TestClient(api.app)

    resp = client.post("/log-batch", json={"runs": [RUN_PAYLOAD]})
    assert resp.status_code == 401

    resp = client.post(
        "/log-batch",
        json={"runs": [RUN_PAYLOAD]},
        headers={"Authorization": "Bearer dev-secret"},
    )
    assert resp.status_code == 200

    config.settings.shared_secret = None  # reset for other tests
