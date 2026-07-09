"""Periodically ship the JSONL chat-turn log to a remote MLflow relay.

The demo box this runs on has no spare inbound ports to expose an MLflow UI
locally, so instead of running MLflow here, this module rotates
``data/observability.jsonl`` out of the way, POSTs its records to
``STAI_LOG_SERVER_URL`` (a small relay API on a separate server, see
``mlflow-relay/src/relay/api.py``), and only deletes the rotated file once
the relay confirms it landed.

Run standalone (intended for a systemd timer - see ``deploy/``):

    uv run python -m stai.log_shipper

No changes to ``TurnRecord`` or ``log_turn`` were needed - the mapping from
chat-turn fields to MLflow's params/metrics/tags model happens entirely here.
One ``TurnRecord`` line becomes one MLflow run (the module already calls
these "runs" - see ``observability.read_runs``).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from stai.config import settings

logger = logging.getLogger(__name__)

EXPERIMENT_NAME = "aisha-chat-turns"

# Fields copied straight onto the MLflow run as string tags, when non-empty.
_TAG_FIELDS = (
    "route",
    "employee_id",
    "agent_model",
    "guardrail_model",
    "guardrail_category",
    "error",
)
# Fields copied straight onto the MLflow run as float metrics.
_METRIC_FIELDS = (
    "message_chars",
    "answer_chars",
    "est_input_tokens",
    "est_output_tokens",
    "latency_ms",
)


def rotate_log(path: Path) -> Path | None:
    """Atomically move the live log aside; ``None`` if there's nothing to ship.

    A rename (not an in-place truncate) avoids racing a concurrent
    ``log_turn()`` append from a live chat turn - the next ``log_turn()``
    call recreates ``path`` fresh on its own.
    """
    if not path.exists() or path.stat().st_size == 0:
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    rotated = path.with_name(f"{path.stem}.{ts}{path.suffix}")
    path.rename(rotated)
    return rotated


def _parse_ts_ms(ts: str) -> int:
    if not ts:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
    return int(datetime.fromisoformat(ts).timestamp() * 1000)


def to_mlflow_payload(record: dict) -> dict:
    """Map one ``TurnRecord`` dict to the relay's run wire schema."""
    tags = {field: str(record[field]) for field in _TAG_FIELDS if record.get(field)}
    if record.get("tools_used"):
        tags["tools_used"] = ",".join(record["tools_used"])
    if record.get("sources"):
        tags["sources"] = ",".join(record["sources"])
    if record.get("escalation_id") is not None:
        tags["escalation_id"] = str(record["escalation_id"])

    metrics = {field: float(record.get(field, 0)) for field in _METRIC_FIELDS}
    metrics["refused"] = 1.0 if record.get("refused") else 0.0
    metrics["plan_changed"] = 1.0 if record.get("plan_changed") else 0.0

    start_ms = _parse_ts_ms(record.get("ts", ""))
    return {
        "experiment_name": EXPERIMENT_NAME,
        "run_name": f"{record.get('employee_id', 'unknown')}-{record.get('ts', '')}",
        "start_time_ms": start_ms,
        "end_time_ms": start_ms + int(record.get("latency_ms", 0)),
        "tags": tags,
        "metrics": metrics,
    }


def ship_batch(rotated_path: Path, url: str, secret: str | None, timeout: float = 30.0) -> bool:
    """POST the rotated file's records to the relay. Returns whether it succeeded."""
    lines = [line for line in rotated_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    runs = [to_mlflow_payload(json.loads(line)) for line in lines]
    body = json.dumps({"runs": runs}).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        logger.warning("Relay rejected batch %s: HTTP %s", rotated_path, exc.code)
        return False
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("Failed to reach relay for %s: %s", rotated_path, exc)
        return False


def run_once(log_path: Path | str | None = None) -> None:
    """Rotate the live log, ship it plus any leftover failed batches.

    Never raises - a shipping failure must not take down the caller, same
    posture as ``TurnObserver.__exit__`` in ``observability.py``.
    """
    path = Path(log_path) if log_path else settings.obs_log_path
    url = settings.log_server_url
    if not url:
        logger.info("STAI_LOG_SERVER_URL not set; skipping log shipping")
        return
    secret = settings.log_shared_secret.get_secret_value() if settings.log_shared_secret else None

    rotated = rotate_log(path)
    pending = sorted(path.parent.glob(f"{path.stem}.*{path.suffix}"))
    if rotated and rotated not in pending:
        pending.append(rotated)

    for batch_path in pending:
        try:
            ok = ship_batch(batch_path, url, secret)
        except Exception:
            logger.exception("Unexpected error shipping %s", batch_path)
            ok = False
        if ok:
            batch_path.unlink(missing_ok=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_once()
