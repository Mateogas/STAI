"""Log shipper: rotate/map/ship logic. No relay or Ollama needed - HTTP is mocked."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError

import pytest

from stai.log_shipper import rotate_log, run_once, ship_batch, to_mlflow_payload
from stai.observability import TurnRecord, log_turn


def test_rotate_log_missing_file_returns_none(tmp_path):
    assert rotate_log(tmp_path / "nope.jsonl") is None


def test_rotate_log_empty_file_returns_none(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text("")
    assert rotate_log(path) is None


def test_rotate_log_renames_and_frees_original_name(tmp_path):
    path = tmp_path / "runs.jsonl"
    log_turn(TurnRecord(route="api", employee_id="emp-alyssa"), path=path)

    rotated = rotate_log(path)

    assert rotated is not None
    assert rotated.exists()
    assert not path.exists()
    assert rotated.name.startswith("runs.") and rotated.name.endswith(".jsonl")

    # a fresh log_turn() call recreates the live file on its own
    log_turn(TurnRecord(route="api", employee_id="emp-jomar"), path=path)
    assert path.exists()


def test_to_mlflow_payload_maps_fields():
    record = TurnRecord(
        ts="2026-07-09T10:00:00+00:00",
        route="api",
        employee_id="emp-alyssa",
        agent_model="llama3.1:8b",
        guardrail_model="qwen2.5:3b-instruct",
        message_chars=21,
        answer_chars=40,
        est_input_tokens=5,
        est_output_tokens=10,
        latency_ms=1500,
        guardrail_category="on_topic",
        refused=False,
        tools_used=["search_knowledge_base"],
        sources=["leave_policy.md"],
        escalation_id=None,
        plan_changed=True,
        error="",
    ).model_dump()

    payload = to_mlflow_payload(record)

    assert payload["experiment_name"] == "aisha-chat-turns"
    assert payload["run_name"] == "emp-alyssa-2026-07-09T10:00:00+00:00"
    assert payload["end_time_ms"] == payload["start_time_ms"] + 1500
    assert payload["tags"]["route"] == "api"
    assert payload["tags"]["tools_used"] == "search_knowledge_base"
    assert payload["tags"]["sources"] == "leave_policy.md"
    assert "escalation_id" not in payload["tags"]  # omitted when None
    assert "error" not in payload["tags"]  # omitted when empty
    assert payload["metrics"]["latency_ms"] == 1500.0
    assert payload["metrics"]["refused"] == 0.0
    assert payload["metrics"]["plan_changed"] == 1.0


def test_to_mlflow_payload_includes_escalation_id_when_set():
    record = TurnRecord(escalation_id=42).model_dump()
    payload = to_mlflow_payload(record)
    assert payload["tags"]["escalation_id"] == "42"


def test_ship_batch_posts_and_returns_true_on_2xx(tmp_path, monkeypatch):
    path = tmp_path / "runs.1.jsonl"
    log_turn(TurnRecord(route="api", employee_id="emp-alyssa"), path=path)

    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setattr("stai.log_shipper.urllib.request.urlopen", fake_urlopen)

    ok = ship_batch(path, "http://relay.example/log-batch", "secret123")

    assert ok is True
    assert captured["url"] == "http://relay.example/log-batch"
    assert captured["headers"]["Authorization"] == "Bearer secret123"
    assert len(captured["body"]["runs"]) == 1


def test_ship_batch_returns_false_on_http_error(tmp_path, monkeypatch):
    path = tmp_path / "runs.1.jsonl"
    log_turn(TurnRecord(route="api"), path=path)

    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 401, "unauthorized", None, None)

    monkeypatch.setattr("stai.log_shipper.urllib.request.urlopen", fake_urlopen)

    assert ship_batch(path, "http://relay.example/log-batch", None) is False


def test_ship_batch_returns_false_on_connection_error(tmp_path, monkeypatch):
    path = tmp_path / "runs.1.jsonl"
    log_turn(TurnRecord(route="api"), path=path)

    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("stai.log_shipper.urllib.request.urlopen", fake_urlopen)

    assert ship_batch(path, "http://relay.example/log-batch", None) is False


@pytest.fixture
def relay_settings(monkeypatch, tmp_path):
    from stai.config import settings

    monkeypatch.setattr(settings, "log_server_url", "http://relay.example/log-batch")
    monkeypatch.setattr(settings, "log_shared_secret", None)
    return settings


def test_run_once_noop_when_url_unset(tmp_path, monkeypatch):
    from stai.config import settings

    monkeypatch.setattr(settings, "log_server_url", None)
    path = tmp_path / "runs.jsonl"
    log_turn(TurnRecord(route="api"), path=path)

    run_once(path)

    assert path.exists()  # nothing rotated away


def test_run_once_ships_and_deletes_on_success(tmp_path, monkeypatch, relay_settings):
    path = tmp_path / "runs.jsonl"
    log_turn(TurnRecord(route="api", employee_id="emp-alyssa"), path=path)

    monkeypatch.setattr("stai.log_shipper.ship_batch", lambda *a, **k: True)

    run_once(path)

    assert not path.exists()
    assert list(tmp_path.glob("runs.*.jsonl")) == []


def test_run_once_keeps_batch_for_retry_on_failure(tmp_path, monkeypatch, relay_settings):
    path = tmp_path / "runs.jsonl"
    log_turn(TurnRecord(route="api", employee_id="emp-alyssa"), path=path)

    monkeypatch.setattr("stai.log_shipper.ship_batch", lambda *a, **k: False)

    run_once(path)

    leftovers = list(tmp_path.glob("runs.*.jsonl"))
    assert len(leftovers) == 1
    assert not path.exists()  # rotated out, but not deleted


def test_run_once_retries_leftover_batches_from_earlier_failures(tmp_path, monkeypatch, relay_settings):
    old_leftover = tmp_path / "runs.20260101T000000000000.jsonl"
    log_turn(TurnRecord(route="api", employee_id="emp-old"), path=old_leftover)

    path = tmp_path / "runs.jsonl"
    log_turn(TurnRecord(route="api", employee_id="emp-new"), path=path)

    shipped = []
    monkeypatch.setattr(
        "stai.log_shipper.ship_batch",
        lambda batch_path, *a, **k: shipped.append(batch_path.name) or True,
    )

    run_once(path)

    assert len(shipped) == 2
    assert old_leftover.name in shipped
    assert list(tmp_path.glob("runs.*.jsonl")) == []
