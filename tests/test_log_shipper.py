"""Bounded telemetry shipper, quarantine, acknowledgement, and retention tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from stai.log_shipper import (
    DeliveryResult,
    cleanup_pending,
    prepare_batch,
    rotate_log,
    run_once,
    to_mlflow_payload,
)
from stai.observability import OperationalTelemetryRecord, log_event


def _event(**changes):
    values = {
        "event_kind": "dialogue",
        "route": "api",
        "actor_kind": "hire",
        "operation": "policy_response",
        "outcome": "grounded_answer",
    }
    values.update(changes)
    return OperationalTelemetryRecord(**values)


def test_rotate_log_is_atomic_and_missing_or_empty_is_noop(tmp_path):
    path = tmp_path / "events.jsonl"
    assert rotate_log(path) is None
    path.write_text("")
    assert rotate_log(path) is None
    log_event(_event(), path)
    rotated = rotate_log(path)
    assert rotated and rotated.exists() and not path.exists()


def test_payload_has_closed_experiment_mapping_and_allowlists():
    payload = to_mlflow_payload(
        _event(duration_ms=12, citation_count=0, page_count=None).model_dump(exclude_none=True)
    )
    assert payload["experiment_name"] == "aisha-chat-turns"
    assert payload["run_name"].startswith("dialogue-")
    assert payload["tags"]["event_kind"] == "dialogue"
    assert payload["metrics"]["citation_count"] == 0.0
    assert "page_count" not in payload["metrics"]
    assert "employee_id" not in json.dumps(payload)


def test_prepare_batch_quarantines_bad_lines_without_blocking_valid(tmp_path):
    path = tmp_path / "events.1.jsonl"
    valid = _event()
    path.write_text(
        valid.model_dump_json(exclude_none=True)
        + "\n{not json}\n"
        + json.dumps({"schema_version": 99})
        + "\n",
        encoding="utf-8",
    )
    batch = prepare_batch(path)
    assert [item["event_id"] for item in batch.events] == [valid.event_id]
    assert batch.quarantined_count == 2
    quarantine = path.with_suffix(path.suffix + ".quarantine")
    assert quarantine.exists()
    assert "malformed_json" in quarantine.read_text()
    assert "unknown_schema_version" in quarantine.read_text()


def test_v1_records_are_sanitized_before_shipping(tmp_path):
    path = tmp_path / "events.1.jsonl"
    path.write_text(json.dumps({
        "schema_version": 1, "route": "api", "employee_id": "emp-alyssa",
        "sources": ["secret.md"], "error": "private error", "latency_ms": 3,
    }) + "\n")
    (payload,) = prepare_batch(path).events
    rendered = json.dumps(payload)
    assert payload["schema_version"] == 2
    assert "emp-alyssa" not in rendered and "secret.md" not in rendered and "private error" not in rendered


def test_partial_ack_rewrites_only_retryable_unacknowledged_records(tmp_path, monkeypatch):
    live = tmp_path / "events.jsonl"
    first, second = _event(), _event()
    log_event(first, live); log_event(second, live)
    monkeypatch.setattr("stai.log_shipper.settings.log_server_url", "http://relay/log-batch")
    monkeypatch.setattr("stai.log_shipper.settings.log_shared_secret", None)
    monkeypatch.setattr(
        "stai.log_shipper.ship_events",
        lambda *a, **k: DeliveryResult(accepted={first.event_id}, already_present=set(), retryable={second.event_id}),
    )
    run_once(live)
    leftovers = list(tmp_path.glob("events.*.jsonl"))
    assert len(leftovers) == 1
    text = leftovers[0].read_text()
    assert second.event_id in text and first.event_id not in text


def test_acknowledged_and_already_present_records_are_deleted(tmp_path, monkeypatch):
    live = tmp_path / "events.jsonl"
    event = _event(); log_event(event, live)
    monkeypatch.setattr("stai.log_shipper.settings.log_server_url", "http://relay/log-batch")
    monkeypatch.setattr("stai.log_shipper.settings.log_shared_secret", None)
    monkeypatch.setattr(
        "stai.log_shipper.ship_events",
        lambda *a, **k: DeliveryResult(accepted=set(), already_present={event.event_id}, retryable=set()),
    )
    run_once(live)
    assert not list(tmp_path.glob("events.*.jsonl"))


def test_retention_deletes_oldest_by_age_and_size(tmp_path):
    now = datetime.now(timezone.utc)
    old = tmp_path / "events.20200101T000000000000.jsonl"
    old.write_text("x" * 20)
    recent_a = tmp_path / "events.20990101T000000000000.jsonl"
    recent_b = tmp_path / "events.20990102T000000000000.jsonl"
    recent_a.write_text("a" * 40); recent_b.write_text("b" * 40)
    old_time = (now - timedelta(days=8)).timestamp()
    import os
    os.utime(old, (old_time, old_time))
    dropped = cleanup_pending(tmp_path, "events", max_age_days=7, max_bytes=50, now=now)
    assert dropped == 2
    assert not old.exists() and not recent_a.exists() and recent_b.exists()


def test_shipper_disabled_is_noop(tmp_path, monkeypatch):
    live = tmp_path / "events.jsonl"; log_event(_event(), live)
    monkeypatch.setattr("stai.log_shipper.settings.log_server_url", None)
    run_once(live)
    assert live.exists()
