"""Authenticated, bounded and idempotent AISHA telemetry relay."""

from __future__ import annotations

import secrets
import uuid
from typing import Literal

import mlflow
from fastapi import Depends, FastAPI, Header, HTTPException
from mlflow.entities import Metric, RunTag
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from pydantic import BaseModel, ConfigDict, Field, model_validator

from relay.config import settings

mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
client = MlflowClient()
app = FastAPI(title="AISHA MLflow telemetry relay")

EXPERIMENTS = {
    "dialogue": "aisha-chat-turns",
    "certificate_check": "aisha-certificate-checks",
    "system_operation": "aisha-system-operations",
    "benchmark_case": "aisha-benchmark",
}
ALLOWED_TAGS = {
    "event_kind", "route", "actor_kind", "operation", "outcome", "error_category",
    "model_release", "prompt_variant", "handbook_release", "benchmark_release",
    "scorer_release", "retrieval_build_release", "benchmark_case_id", "partition",
    "onboarding_topic", "policy_response", "applicability", "guardrail_category",
    "retrieval_outcome", "escalation_progression", "http_status_class", "tool_names",
}
ALLOWED_METRICS = {
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


class RunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(max_length=36)
    event_kind: Literal["dialogue", "certificate_check", "system_operation", "benchmark_case"]
    experiment_name: Literal[
        "aisha-chat-turns", "aisha-certificate-checks",
        "aisha-system-operations", "aisha-benchmark",
    ] | None = None
    run_name: str = Field(min_length=1, max_length=100)
    start_time_ms: int = Field(ge=0)
    end_time_ms: int = Field(ge=0)
    tags: dict[str, str] = Field(default_factory=dict, max_length=32)
    metrics: dict[str, float] = Field(default_factory=dict, max_length=64)

    @model_validator(mode="after")
    def closed_payload(self):
        uuid.UUID(self.event_id)
        if self.end_time_ms < self.start_time_ms:
            raise ValueError("end_time_ms precedes start_time_ms")
        expected = EXPERIMENTS[self.event_kind]
        if self.experiment_name is not None and self.experiment_name != expected:
            raise ValueError("experiment does not match event kind")
        if not set(self.tags) <= ALLOWED_TAGS or not set(self.metrics) <= ALLOWED_METRICS:
            raise ValueError("unknown telemetry field")
        if any(len(key) > 64 or len(value) > 128 for key, value in self.tags.items()):
            raise ValueError("tag bound exceeded")
        if any(len(key) > 64 for key in self.metrics):
            raise ValueError("metric bound exceeded")
        return self


class LogBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runs: list[RunPayload] = Field(min_length=1, max_length=100)


class LogBatchResponse(BaseModel):
    accepted_event_ids: list[str]
    already_present_event_ids: list[str]
    retryable_event_ids: list[str]


class HealthResponse(BaseModel):
    status: str
    mlflow_reachable: bool


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    if settings.shared_secret is None:
        return
    expected = f"Bearer {settings.shared_secret.get_secret_value()}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")


def _get_or_create_experiment(name: str) -> str:
    experiment = client.get_experiment_by_name(name)
    return experiment.experiment_id if experiment else client.create_experiment(name)


def _already_present(payload: RunPayload) -> bool:
    experiment = client.get_experiment_by_name(EXPERIMENTS[payload.event_kind])
    if experiment is None:
        return False
    escaped = payload.event_id.replace("'", "")
    return bool(client.search_runs([experiment.experiment_id], filter_string=f"tags.event_id = '{escaped}'", max_results=1))


def _log_one_run(payload: RunPayload) -> None:
    experiment_id = _get_or_create_experiment(EXPERIMENTS[payload.event_kind])
    run = client.create_run(experiment_id=experiment_id, start_time=payload.start_time_ms)
    run_id = run.info.run_id
    tags = dict(payload.tags)
    tags["event_id"] = payload.event_id
    client.set_tag(run_id, "mlflow.runName", payload.run_name)
    metrics = [Metric(key, value, payload.end_time_ms, 0) for key, value in payload.metrics.items()]
    run_tags = [RunTag(key, value) for key, value in tags.items()]
    try:
        client.log_batch(run_id, metrics=metrics, tags=run_tags)
    except MlflowException:
        for metric in metrics:
            client.log_metric(run_id, metric.key, metric.value, timestamp=metric.timestamp, step=0)
        for tag in run_tags:
            client.set_tag(run_id, tag.key, tag.value)
    client.set_terminated(run_id, status="FINISHED", end_time=payload.end_time_ms)


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
    accepted: list[str] = []
    present: list[str] = []
    retryable: list[str] = []
    for payload in req.runs:
        try:
            if _already_present(payload):
                present.append(payload.event_id)
                continue
            _log_one_run(payload)
            accepted.append(payload.event_id)
        except Exception:
            retryable.append(payload.event_id)
    return LogBatchResponse(
        accepted_event_ids=accepted,
        already_present_event_ids=present,
        retryable_event_ids=retryable,
    )
