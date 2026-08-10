"""Bounded rotating shipper for privacy-safe Operational Telemetry Records."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from stai.config import settings
from stai.observability import OperationalTelemetryRecord, parse_record

logger = logging.getLogger(__name__)

MAX_EVENTS = 100
MAX_BATCH_BYTES = 1_000_000
MAX_PENDING_BYTES = 100 * 1024 * 1024

EXPERIMENTS = {
    "dialogue": "aisha-chat-turns",
    "certificate_check": "aisha-certificate-checks",
    "system_operation": "aisha-system-operations",
    "benchmark_case": "aisha-benchmark",
}
TAG_FIELDS = {
    "event_kind", "route", "actor_kind", "operation", "outcome", "error_category",
    "model_release", "prompt_variant", "handbook_release", "benchmark_release",
    "scorer_release", "retrieval_build_release", "benchmark_case_id", "partition",
    "onboarding_topic", "policy_response", "applicability", "guardrail_category",
    "retrieval_outcome", "escalation_progression", "http_status_class",
}
METRIC_FIELDS = {
    "duration_ms", "input_char_count", "output_char_count", "estimated_input_tokens",
    "estimated_output_tokens", "tool_call_count", "material_claim_count",
    "supported_claim_count", "citation_count", "candidate_count", "eligible_count",
    "evidence_count", "rejected_count", "clarification_count", "calendar_year",
    "retry_count", "result_count", "accepted_attempt_count", "page_count", "repetition",
    "dense_ms", "lexical_ms", "eligibility_ms", "reranking_ms", "claim_validation_ms",
    "preflight_ms", "extraction_ms", "rendering_ms", "ocr_ms", "validation_ms",
    "cleanup_ms", "persistence_ms", "calendar_context_used", "tool_correctly_deferred",
    "retry_used", "assertion_passed",
}


@dataclass(frozen=True)
class PreparedBatch:
    events: list[dict[str, Any]]
    quarantined_count: int


@dataclass(frozen=True)
class DeliveryResult:
    accepted: set[str]
    already_present: set[str]
    retryable: set[str]


def rotate_log(path: Path) -> Path | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    rotated = path.with_name(f"{path.stem}.{suffix}{path.suffix}")
    path.rename(rotated)
    return rotated


def _quarantine(path: Path, line_number: int, reason: str) -> None:
    # Never copy the invalid line: it may contain the exact content v2 forbids.
    with path.with_suffix(path.suffix + ".quarantine").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"line": line_number, "reason": reason}, separators=(",", ":")) + "\n")


def prepare_batch(path: Path) -> PreparedBatch:
    events: list[dict[str, Any]] = []
    quarantined = 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            _quarantine(path, number, "malformed_json")
            quarantined += 1
            continue
        try:
            record = parse_record(raw)
        except ValueError as exc:
            reason = "unknown_schema_version" if str(exc) == "unknown_schema_version" else "schema_validation_failure"
            _quarantine(path, number, reason)
            quarantined += 1
            continue
        except ValidationError:
            _quarantine(path, number, "schema_validation_failure")
            quarantined += 1
            continue
        events.append(record.model_dump(exclude_none=True, mode="json"))
    return PreparedBatch(events=events, quarantined_count=quarantined)


def _parse_ts_ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def to_mlflow_payload(record: dict[str, Any]) -> dict[str, Any]:
    parsed = OperationalTelemetryRecord.model_validate(record)
    safe = parsed.model_dump(exclude_none=True, mode="json")
    tags = {key: str(safe[key])[:128] for key in TAG_FIELDS if key in safe}
    if parsed.tool_names:
        tags["tool_names"] = ",".join(parsed.tool_names)
    metrics = {
        key: float(safe[key])
        for key in METRIC_FIELDS
        if key in safe and isinstance(safe[key], (int, float, bool))
    }
    start = _parse_ts_ms(parsed.started_at_utc)
    duration = parsed.duration_ms or 0
    stamp = datetime.fromtimestamp(start / 1000, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "event_id": parsed.event_id,
        "event_kind": parsed.event_kind,
        "experiment_name": EXPERIMENTS[parsed.event_kind],
        "run_name": f"{parsed.event_kind}-{stamp}-{parsed.event_id[:8]}",
        "start_time_ms": start,
        "end_time_ms": start + duration,
        "tags": tags,
        "metrics": metrics,
    }


def ship_events(events: list[dict[str, Any]], url: str, secret: str | None, timeout: float = 30.0) -> DeliveryResult:
    payloads = [to_mlflow_payload(event) for event in events[:MAX_EVENTS]]
    body = json.dumps({"runs": payloads}, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_BATCH_BYTES:
        return DeliveryResult(set(), set(), {event["event_id"] for event in events})
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, OSError):
        return DeliveryResult(set(), set(), {event["event_id"] for event in events})
    return DeliveryResult(
        accepted=set(data.get("accepted_event_ids", [])),
        already_present=set(data.get("already_present_event_ids", [])),
        retryable=set(data.get("retryable_event_ids", [])),
    )


def cleanup_pending(
    directory: Path,
    stem: str,
    *,
    max_age_days: int = 7,
    max_bytes: int = MAX_PENDING_BYTES,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(timezone.utc)
    paths = sorted(directory.glob(f"{stem}.*.jsonl"), key=lambda item: item.stat().st_mtime)
    dropped = 0
    cutoff = now - timedelta(days=max_age_days)
    for path in list(paths):
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if modified < cutoff:
            path.unlink(missing_ok=True); paths.remove(path); dropped += 1
    total = sum(path.stat().st_size for path in paths)
    while paths and total > max_bytes:
        path = paths.pop(0); total -= path.stat().st_size; path.unlink(missing_ok=True); dropped += 1
    return dropped


def run_once(log_path: Path | str | None = None) -> None:
    """Rotate, sanitize, ship and retain records; never raise into the product."""
    path = Path(log_path) if log_path else settings.obs_log_path
    if not settings.log_server_url:
        return
    try:
        rotate_log(path)
        cleanup_pending(path.parent, path.stem)
        secret = settings.log_shared_secret.get_secret_value() if settings.log_shared_secret else None
        for batch_path in sorted(path.parent.glob(f"{path.stem}.*{path.suffix}")):
            prepared = prepare_batch(batch_path)
            if not prepared.events:
                batch_path.unlink(missing_ok=True)
                continue
            result = ship_events(prepared.events, settings.log_server_url, secret)
            delivered = result.accepted | result.already_present
            retry = [event for event in prepared.events if event["event_id"] not in delivered]
            if retry:
                batch_path.write_text(
                    "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in retry),
                    encoding="utf-8",
                )
            else:
                batch_path.unlink(missing_ok=True)
    except Exception:
        logger.warning("telemetry shipping failed safely")


# One release of sender compatibility.
ship_batch = ship_events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_once()
