"""MLflow log relay: receives batched chat-turn runs, replays them into MLflow.

Run:  uv run uvicorn relay.api:app --host 0.0.0.0 --port 8080
Docs: http://localhost:8080/docs

Requires a separately-running ``mlflow server`` reachable at
``RELAY_MLFLOW_TRACKING_URI`` (see ``deploy/docker-compose.yml``). The sender
side lives in the STAI repo: ``src/stai/log_shipper.py``.

Each item in a batch is a complete, one-shot MLflow run: create -> log_batch
-> terminate, all within one relay call. There is no run-mapping or
idempotency store - a retried batch just creates duplicate runs, which is an
acceptable cost given the sender only retries a batch it never got a 2xx
response for.
"""

from __future__ import annotations

import secrets

import mlflow
from fastapi import Depends, FastAPI, Header, HTTPException
from mlflow.entities import Metric, RunTag
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from pydantic import BaseModel

from relay.config import settings

mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
client = MlflowClient()

app = FastAPI(title="AISHA MLflow log relay")


# ------------------------------------------------------------------ schemas


class RunPayload(BaseModel):
    experiment_name: str
    run_name: str
    start_time_ms: int
    end_time_ms: int
    tags: dict[str, str] = {}
    metrics: dict[str, float] = {}


class LogBatchRequest(BaseModel):
    runs: list[RunPayload]


class LogBatchResponse(BaseModel):
    created: int


class HealthResponse(BaseModel):
    status: str
    mlflow_reachable: bool


# --------------------------------------------------------------- auth + mlflow


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    if settings.shared_secret is None:
        return  # no secret configured -> auth disabled (dev only)
    expected = f"Bearer {settings.shared_secret.get_secret_value()}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")


def _get_or_create_experiment(name: str) -> str:
    experiment = client.get_experiment_by_name(name)
    return experiment.experiment_id if experiment else client.create_experiment(name)


def _log_one_run(payload: RunPayload) -> None:
    experiment_id = _get_or_create_experiment(payload.experiment_name)
    run = client.create_run(experiment_id=experiment_id, start_time=payload.start_time_ms)
    run_id = run.info.run_id
    client.set_tag(run_id, "mlflow.runName", payload.run_name)

    metrics = [Metric(k, v, payload.end_time_ms, 0) for k, v in payload.metrics.items()]
    tags = [RunTag(k, v) for k, v in payload.tags.items()]
    try:
        client.log_batch(run_id, metrics=metrics, tags=tags)
    except MlflowException:
        # log_batch is all-or-nothing; fall back to per-item calls so one bad
        # entry (e.g. an immutable param collision) doesn't drop the rest.
        for metric in metrics:
            client.log_metric(run_id, metric.key, metric.value, timestamp=metric.timestamp, step=metric.step)
        for tag in tags:
            client.set_tag(run_id, tag.key, tag.value)

    client.set_terminated(run_id, status="FINISHED", end_time=payload.end_time_ms)


# ---------------------------------------------------------------- endpoints


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        client.search_experiments(max_results=1)
        reachable = True
    except Exception:
        reachable = False
    return HealthResponse(status="ok", mlflow_reachable=reachable)


@app.post("/log-batch", response_model=LogBatchResponse, dependencies=[Depends(require_api_key)])
def log_batch(req: LogBatchRequest) -> LogBatchResponse:
    try:
        for payload in req.runs:
            _log_one_run(payload)
    except MlflowException as exc:
        raise HTTPException(status_code=502, detail=f"MLflow error: {exc}") from exc
    return LogBatchResponse(created=len(req.runs))
