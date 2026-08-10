"""Schema-v2 operational telemetry privacy and failure-isolation tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from stai.observability import (
    OperationalTelemetryRecord,
    TelemetryObserver,
    estimate_tokens,
    log_event,
    read_events,
    sanitize_v1_record,
)


def test_v2_round_trip_omits_inapplicable_metrics(tmp_path):
    path = tmp_path / "events.jsonl"
    event = OperationalTelemetryRecord(
        event_kind="dialogue",
        route="api",
        actor_kind="hire",
        operation="policy_response",
        outcome="grounded_answer",
        duration_ms=42,
        tool_names=["search_handbook"],
        tool_call_count=1,
        citation_count=0,
    )
    log_event(event, path)
    (saved,) = read_events(path)
    assert saved["schema_version"] == 2
    assert saved["event_id"] == event.event_id
    assert saved["citation_count"] == 0
    assert "page_count" not in saved
    assert "employee_id" not in json.dumps(saved)


def test_v1_mapper_sanitizes_identity_content_sources_and_raw_error():
    converted = sanitize_v1_record(
        {
            "schema_version": 1,
            "ts": "2026-08-10T00:00:00+00:00",
            "route": "api",
            "employee_id": "emp-alyssa",
            "message_chars": 12,
            "answer_chars": 20,
            "latency_ms": 10,
            "guardrail_category": "on_topic",
            "tools_used": ["search_knowledge_base", "evil_tool"],
            "sources": ["policy-secret.md"],
            "error": "RuntimeError: private upload /tmp/a.pdf",
            "plan_changed": True,
        }
    ).model_dump(exclude_none=True)
    rendered = json.dumps(converted)
    assert converted["schema_version"] == 2
    assert converted["tool_names"] == ["search_handbook"]
    assert converted["error_category"] == "unexpected_internal"
    for secret in ("emp-alyssa", "policy-secret", "/tmp/a.pdf", "plan_changed", "sources"):
        assert secret not in rendered


@pytest.mark.parametrize(
    "unsafe",
    [
        {"employee_id": "emp-alyssa"},
        {"sources": ["PAY-001"]},
        {"filename": "certificate.pdf"},
        {"ocr_text": "diagnosis"},
        {"error": "raw stack"},
        {"policy_id": "PAY-001"},
    ],
)
def test_v2_denylist_and_extra_fields_fail_closed(unsafe):
    with pytest.raises(ValidationError):
        OperationalTelemetryRecord(
            event_kind="dialogue",
            route="api",
            actor_kind="hire",
            operation="policy_response",
            outcome="grounded_answer",
            **unsafe,
        )


def test_closed_enums_and_tool_allowlist_reject_arbitrary_values():
    with pytest.raises(ValidationError):
        OperationalTelemetryRecord(
            event_kind="dialogue",
            route="api",
            actor_kind="hire",
            operation="free_form_operation",
            outcome="grounded_answer",
        )
    with pytest.raises(ValidationError):
        OperationalTelemetryRecord(
            event_kind="dialogue",
            route="api",
            actor_kind="hire",
            operation="policy_response",
            outcome="grounded_answer",
            tool_names=["shell"],
        )


def test_observer_maps_raw_exception_and_never_swallows_it(tmp_path):
    path = tmp_path / "events.jsonl"
    with pytest.raises(RuntimeError):
        with TelemetryObserver(
            path=path,
            event_kind="dialogue",
            route="streamlit",
            actor_kind="hire",
            operation="policy_response",
        ):
            raise RuntimeError("private message and /secret/path")
    (saved,) = read_events(path)
    assert saved["outcome"] == "failed"
    assert saved["error_category"] == "unexpected_internal"
    assert "private message" not in json.dumps(saved)


def test_observer_write_failure_cannot_change_product_outcome(tmp_path, monkeypatch):
    monkeypatch.setattr("stai.observability.log_event", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    with TelemetryObserver(
        path=tmp_path / "events.jsonl",
        event_kind="dialogue",
        route="api",
        actor_kind="hire",
        operation="policy_response",
    ) as observer:
        observer.record.outcome = "grounded_answer"
    assert observer.record.outcome == "grounded_answer"


def test_estimate_tokens_is_explicitly_an_estimate():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hi") == 1
    assert estimate_tokens("a" * 400) == 100
