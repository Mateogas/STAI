"""Privacy-safe, failure-isolated operational telemetry.

The product emits one schema-v2 record per top-level operation.  Records are
closed metadata: they cannot identify a Hire or reconstruct chat, policy,
retrieval, escalation, or certificate content.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from stai.config import settings


EventKind = Literal["dialogue", "certificate_check", "system_operation", "benchmark_case"]
Route = Literal["streamlit", "api", "worker", "benchmark"]
ActorKind = Literal["hire", "hr_user", "system", "benchmark"]
Operation = Literal[
    "policy_response", "certificate_preflight", "certificate_validation",
    "validation_result_action", "retrieval", "index_build", "index_verify",
    "index_activate", "index_rollback", "calendar_lookup", "benchmark_assertion",
    "escalation_action", "attribute_action", "history_action", "unknown",
]
Outcome = Literal[
    "grounded_answer", "clarification_request", "abstention", "escalation_offer",
    "consented", "declined", "complete", "incomplete", "needs_human_review",
    "upload_rejection", "check_failure", "ready", "insufficient_evidence",
    "required_hire_attribute", "policy_conflict", "knowledge_index_outage",
    "integrity_failure", "handbook_omission", "live", "cache", "unavailable",
    "verified", "activated", "rolled_back", "passed", "failed", "unknown",
]
ErrorCategory = Literal[
    "guardrail_unavailable", "guardrail_invalid_output", "model_unavailable",
    "model_timeout", "model_invalid_output", "retrieval_unavailable",
    "retrieval_integrity_failure", "retrieval_internal_failure", "calendar_timeout",
    "calendar_http_failure", "calendar_invalid_response", "calendar_circuit_open",
    "pdf_extraction_failure", "rendering_failure", "ocr_failure",
    "validation_configuration_failure", "cleanup_failure", "persistence_failure",
    "schema_serialization_failure", "relay_authentication_failure",
    "relay_validation_failure", "relay_rate_size_rejection",
    "relay_downstream_unavailable", "relay_timeout", "unexpected_internal",
]

ALLOWED_TOOLS = {
    "search_handbook", "get_active_handbook", "lookup_public_holidays",
    "evaluate_applicability", "offer_escalation",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def estimate_tokens(text: str) -> int:
    """Return a clearly labelled rough token estimate (~4 characters/token)."""
    return 0 if not text else max(1, len(text) // 4)


class OperationalTelemetryRecord(BaseModel):
    """The only accepted local observer record schema."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: Literal[2] = 2
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=36)
    started_at_utc: str = Field(default_factory=_utc_now, max_length=40)
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    event_kind: EventKind
    route: Route
    actor_kind: ActorKind
    operation: Operation
    outcome: Outcome = "unknown"
    error_category: ErrorCategory | None = None

    model_release: str | None = Field(default=None, max_length=80)
    prompt_variant: Literal["P1", "P2", "P3"] | None = None
    handbook_release: str | None = Field(default=None, max_length=40)
    benchmark_release: str | None = Field(default=None, max_length=40)
    scorer_release: str | None = Field(default=None, max_length=40)
    retrieval_build_release: str | None = Field(default=None, max_length=40)
    benchmark_case_id: str | None = Field(default=None, pattern=r"^[A-Z]{3}-\d{2}$")
    partition: Literal["calibration", "locked"] | None = None
    repetition: int | None = Field(default=None, ge=1, le=3)

    input_char_count: int | None = Field(default=None, ge=0, le=1_000_000)
    output_char_count: int | None = Field(default=None, ge=0, le=1_000_000)
    estimated_input_tokens: int | None = Field(default=None, ge=0, le=1_000_000)
    estimated_output_tokens: int | None = Field(default=None, ge=0, le=1_000_000)
    tool_names: list[str] | None = Field(default=None, max_length=8)
    tool_call_count: int | None = Field(default=None, ge=0, le=100)

    onboarding_topic: Literal["payroll", "resource_access", "hr_policies"] | None = None
    policy_response: Literal["grounded_answer", "clarification_request", "abstention", "escalation_offer"] | None = None
    applicability: Literal["applies", "does_not_apply", "needs_clarification"] | None = None
    guardrail_category: Literal["on_topic", "off_topic", "injection", "medical_content", "unknown"] | None = None
    retrieval_outcome: Literal[
        "ready", "insufficient_evidence", "required_hire_attribute", "policy_conflict",
        "knowledge_index_outage", "integrity_failure", "handbook_omission",
    ] | None = None
    escalation_progression: Literal["none", "offered", "consented", "declined", "failed"] | None = None
    calendar_context_used: bool | None = None

    material_claim_count: int | None = Field(default=None, ge=0, le=1000)
    supported_claim_count: int | None = Field(default=None, ge=0, le=1000)
    citation_count: int | None = Field(default=None, ge=0, le=1000)
    candidate_count: int | None = Field(default=None, ge=0, le=100_000)
    eligible_count: int | None = Field(default=None, ge=0, le=100_000)
    evidence_count: int | None = Field(default=None, ge=0, le=100_000)
    rejected_count: int | None = Field(default=None, ge=0, le=100_000)
    clarification_count: int | None = Field(default=None, ge=0, le=10)
    tool_correctly_deferred: bool | None = None

    calendar_year: int | None = Field(default=None, ge=2000, le=2200)
    http_status_class: Literal["2xx", "4xx", "5xx"] | None = None
    retry_count: int | None = Field(default=None, ge=0, le=3)
    result_count: int | None = Field(default=None, ge=0, le=500)
    accepted_attempt_count: int | None = Field(default=None, ge=0, le=2)
    retry_used: bool | None = None
    page_count: int | None = Field(default=None, ge=0, le=3)
    assertion_passed: bool | None = None

    dense_ms: int | None = Field(default=None, ge=0)
    lexical_ms: int | None = Field(default=None, ge=0)
    eligibility_ms: int | None = Field(default=None, ge=0)
    reranking_ms: int | None = Field(default=None, ge=0)
    claim_validation_ms: int | None = Field(default=None, ge=0)
    preflight_ms: int | None = Field(default=None, ge=0)
    extraction_ms: int | None = Field(default=None, ge=0)
    rendering_ms: int | None = Field(default=None, ge=0)
    ocr_ms: int | None = Field(default=None, ge=0)
    validation_ms: int | None = Field(default=None, ge=0)
    cleanup_ms: int | None = Field(default=None, ge=0)
    persistence_ms: int | None = Field(default=None, ge=0)

    @field_validator("event_id")
    @classmethod
    def valid_random_uuid(cls, value: str) -> str:
        if str(uuid.UUID(value)) != value.lower():
            raise ValueError("event_id must be a canonical UUID")
        return value

    @field_validator("tool_names")
    @classmethod
    def closed_tools(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (len(value) != len(set(value)) or not set(value) <= ALLOWED_TOOLS):
            raise ValueError("tool names must be unique members of the closed allowlist")
        return value


def sanitize_v1_record(record: dict[str, Any]) -> OperationalTelemetryRecord:
    """Convert the immediately previous schema without forwarding unsafe data."""
    route = record.get("route") if record.get("route") in {"api", "streamlit"} else "worker"
    legacy_tools = {
        "search_knowledge_base": "search_handbook",
        "get_active_handbook": "get_active_handbook",
        "lookup_public_holidays": "lookup_public_holidays",
    }
    tools = []
    for name in record.get("tools_used") or []:
        mapped = legacy_tools.get(name)
        if mapped and mapped not in tools:
            tools.append(mapped)
    failed = bool(record.get("error"))
    refused = bool(record.get("refused"))
    outcome: Outcome = "failed" if failed else ("abstention" if refused else "unknown")
    category = record.get("guardrail_category")
    if category not in {"on_topic", "off_topic", "injection", "medical_content", "unknown"}:
        category = "unknown"
    return OperationalTelemetryRecord(
        started_at_utc=record.get("ts") or _utc_now(),
        event_kind="dialogue",
        route=route,
        actor_kind="hire",
        operation="policy_response",
        outcome=outcome,
        error_category="unexpected_internal" if failed else None,
        duration_ms=max(0, int(record.get("latency_ms") or 0)),
        input_char_count=max(0, int(record.get("message_chars") or 0)),
        output_char_count=max(0, int(record.get("answer_chars") or 0)),
        estimated_input_tokens=max(0, int(record.get("est_input_tokens") or 0)),
        estimated_output_tokens=max(0, int(record.get("est_output_tokens") or 0)),
        guardrail_category=category,
        tool_names=tools or None,
        tool_call_count=len(tools),
    )


def parse_record(record: dict[str, Any]) -> OperationalTelemetryRecord:
    version = record.get("schema_version", 1)
    if version == 1:
        return sanitize_v1_record(record)
    if version != 2:
        raise ValueError("unknown_schema_version")
    return OperationalTelemetryRecord.model_validate(record)


def log_event(record: OperationalTelemetryRecord, path: Path | str | None = None) -> Path:
    log_path = Path(path) if path else settings.obs_log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json(exclude_none=True) + "\n")
    return log_path


def read_events(path: Path | str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    log_path = Path(path) if path else settings.obs_log_path
    if not log_path.exists():
        return []
    values = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return values[-limit:] if limit else values


class TelemetryObserver:
    """Time one top-level operation without ever changing its product result."""

    def __init__(self, path: Path | str | None = None, **fields: Any) -> None:
        self.record = OperationalTelemetryRecord(**fields)
        self._path = path
        self._start = 0.0

    def __enter__(self) -> "TelemetryObserver":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, _tb) -> bool:
        self.record.duration_ms = int((time.perf_counter() - self._start) * 1000)
        if exc is not None:
            self.record.outcome = "failed"
            self.record.error_category = "unexpected_internal"
        try:
            log_event(self.record, self._path)
        except Exception:
            pass
        return False


# Compatibility names are code aliases only; all emitted records are v2.
TurnRecord = OperationalTelemetryRecord
TurnObserver = TelemetryObserver
log_turn = log_event
read_runs = read_events
