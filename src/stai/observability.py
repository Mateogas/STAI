"""Local-first LLMOps: append-only JSONL run logs for every chat turn.

Why JSONL instead of MLflow: the whole demo is local-first and offline
(Ollama + Chroma + SQLite), and the observability requirement is traces,
latency, token estimates, tool usage, and errors - not experiment tracking.
MLflow would add a heavy dependency tree plus a tracking server/UI process to
a demo whose install story is already fragile (OneDrive file locks). A flat
JSONL file is greppable, loads straight into pandas for analysis, and this
module isolates the sink so swapping ``log_turn`` for an MLflow client later
is a one-function change.

Token counts: Ollama via LangChain does not reliably report usage on every
response, so tokens are *estimated* from text length (~4 chars/token). The
records say ``est_*`` on purpose.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from stai.config import settings


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token, minimum 1 for any text."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class TurnRecord(BaseModel):
    """One logged chat turn (or failed attempt)."""

    ts: str = ""
    route: str = "unknown"  # "streamlit" | "api"
    employee_id: str = ""
    agent_model: str = ""
    guardrail_model: str = ""
    message_chars: int = 0
    answer_chars: int = 0
    est_input_tokens: int = 0
    est_output_tokens: int = 0
    latency_ms: int = 0
    guardrail_category: str = ""
    refused: bool = False
    tools_used: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    escalation_id: int | None = None
    plan_changed: bool = False
    error: str = ""


def log_turn(record: TurnRecord, path: Path | str | None = None) -> Path:
    """Append one record to the JSONL run log; returns the log path."""
    log_path = Path(path) if path else settings.obs_log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not record.ts:
        record.ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(record.model_dump_json() + "\n")
    return log_path


def read_runs(path: Path | str | None = None, limit: int | None = None) -> list[dict]:
    """Load logged runs (most recent last). Tolerates a missing file."""
    log_path = Path(path) if path else settings.obs_log_path
    if not log_path.exists():
        return []
    runs: list[dict] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            runs.append(json.loads(line))
    return runs[-limit:] if limit else runs


class TurnObserver:
    """Context manager that times one chat turn and writes a ``TurnRecord``.

    Usage::

        with TurnObserver(route="api", employee_id=emp.id) as obs:
            ... run the turn, then fill obs.record fields ...

    Latency is measured from ``__enter__`` to ``__exit__``. An exception inside
    the block is recorded (class + message) and re-raised.
    """

    def __init__(self, path: Path | str | None = None, **fields: Any) -> None:
        self.record = TurnRecord(
            agent_model=settings.agent_model,
            guardrail_model=settings.guardrail_model,
            **fields,
        )
        self._path = path
        self._start = 0.0

    def __enter__(self) -> "TurnObserver":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, _tb) -> bool:
        self.record.latency_ms = int((time.perf_counter() - self._start) * 1000)
        if exc is not None:
            self.record.error = f"{exc_type.__name__}: {exc}"
        try:
            log_turn(self.record, path=self._path)
        except OSError:
            pass  # observability must never take down the chat turn
        return False
