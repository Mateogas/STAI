"""Typed fictional-demo REST API shared with the AISHA Streamlit service."""

from __future__ import annotations

import json
import uuid
from datetime import date
from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from stai.config import settings
from stai.handbook import build_handbook
from stai.models import ApplicabilityStatus
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import IdempotencyConflict, MedicalContentRejected, Repo


API_VERSION = "v1"
DISCLAIMER = (
    "AISHA is a fictional educational capstone prototype. It is not affiliated "
    "with, endorsed by, or representative of BDO Unibank."
)

app = FastAPI(
    title="AISHA - AI Support for Hires and Associates",
    description=DISCLAIMER,
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "X-Request-ID"],
)


@app.middleware("http")
async def request_identity(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    return await call_next(request)


def _meta(request: Request, simulated_date: str | None = None) -> dict:
    meta = {"request_id": request.state.request_id, "api_version": API_VERSION}
    if simulated_date:
        meta["simulated_date"] = simulated_date
    return meta


def success(request: Request, data, *, status: int = 200, simulated_date: str | None = None):
    return JSONResponse(status_code=status, content={"data": data, "meta": _meta(request, simulated_date)})


def safe_error(request: Request, status: int, code: str, message: str, *, retryable: bool = False, fields: list[str] | None = None):
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "retryable": retryable, "fields": fields or []},
            "meta": _meta(request),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, _exc: RequestValidationError):
    return safe_error(request, 422, "invalid_request", "One or more request fields are invalid.")


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_failed", "message": "The request could not be completed."}
    return safe_error(request, exc.status_code, detail.get("code", "request_failed"), detail.get("message", "The request could not be completed."), retryable=detail.get("retryable", False), fields=detail.get("fields", []))


@app.exception_handler(Exception)
async def unexpected_error(request: Request, _exc: Exception):
    return safe_error(request, 500, "unexpected_internal", "AISHA could not complete the request safely.", retryable=True)


@lru_cache(maxsize=1)
def get_repo() -> Repo:
    return Repo()


@lru_cache(maxsize=1)
def get_service() -> AishaService:
    artifacts = build_handbook()
    return AishaService(get_repo(), load_page_records(artifacts.rag_pages_path))


def _hire(employee_id: str) -> None:
    if employee_id != "emp-alyssa":
        raise HTTPException(404, {"code": "hire_not_found", "message": "The demo Hire was not found."})


def _key(value: str | None) -> str:
    if not value or len(value) > 200:
        raise HTTPException(422, {"code": "idempotency_key_required", "message": "A valid Idempotency-Key is required."})
    return value


def _canonical(value: BaseModel | dict) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class ConversationCreate(BaseModel):
    simulated_date: date


class MessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class VersionAction(BaseModel):
    expected_version: int = Field(ge=1)


class AttributeCreate(BaseModel):
    attribute_name: str
    proposed_value: str
    consent: bool


class AttributeResolve(VersionAction):
    expected_profile_revision: int = Field(ge=1)
    hr_user: str = Field(min_length=1, max_length=80)


@app.get("/api/v1/health")
def health(request: Request, repo: Repo = Depends(get_repo)):
    sqlite_state = "ready"
    try:
        active = repo.get_active_retrieval_build()
    except Exception:
        sqlite_state, active = "unavailable", None
    index_state = "ready" if active else "unavailable"
    status = "ready" if sqlite_state == index_state == "ready" else "unavailable"
    code = 200 if status == "ready" else 503
    return success(
        request,
        {
            "status": status,
            "sqlite": sqlite_state,
            "knowledge_index": index_state,
            "active_handbook_version": active["handbook_version"] if active else None,
            "agent_model": "configured",
            "guardrail_model": "configured",
            "nager": "unknown",
            "disclaimer": DISCLAIMER,
        },
        status=code,
    )


@app.post("/api/v1/hires/{employee_id}/conversations")
def create_conversation(
    employee_id: str, body: ConversationCreate, request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service),
):
    _hire(employee_id)
    key = _key(idempotency_key)
    scope, canonical = f"conversation:create:{employee_id}", _canonical(body)
    try:
        replay = repo.check_idempotency(scope, key, canonical)
    except IdempotencyConflict:
        return safe_error(request, 409, "idempotency_conflict", "This idempotency key was already used with different input.")
    if replay:
        row = repo.get_policy_conversation(replay["target_resource_id"])
        data = {"id": row["conversation_id"], "employee_id": row["hire_id"], "simulated_date": row["simulated_date"], "version": row["resource_version"]}
        return success(request, data, status=201, simulated_date=row["simulated_date"])
    data = service.create_conversation(employee_id, body.simulated_date)
    repo.save_idempotency(scope, key, canonical, target_type="conversation", target_id=data["id"], target_version=1, http_status=201, outcome_code="created")
    return success(request, data, status=201, simulated_date=data["simulated_date"])


@app.get("/api/v1/hires/{employee_id}/conversations")
def list_conversations(employee_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id)
    with repo.connection() as conn:
        rows = conn.execute("SELECT conversation_id,simulated_date,created_at_utc,updated_at_utc,resource_version FROM policy_conversations WHERE hire_id=? ORDER BY created_at_utc DESC, conversation_id DESC LIMIT 20", (employee_id,)).fetchall()
    return success(request, {"items": [dict(row) for row in rows], "next_cursor": None})


@app.get("/api/v1/hires/{employee_id}/conversations/{conversation_id}")
def get_conversation(employee_id: str, conversation_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id)
    row = repo.get_policy_conversation(conversation_id)
    if not row or row["hire_id"] != employee_id:
        return safe_error(request, 404, "conversation_not_found", "The conversation was not found.")
    return success(request, {"id": row["conversation_id"], "employee_id": row["hire_id"], "simulated_date": row["simulated_date"], "version": row["resource_version"]}, simulated_date=row["simulated_date"])


@app.get("/api/v1/hires/{employee_id}/conversations/{conversation_id}/messages")
def list_messages(employee_id: str, conversation_id: str, request: Request, service: AishaService = Depends(get_service)):
    _hire(employee_id)
    items = service.list_messages(conversation_id)
    return success(request, {"items": items, "next_cursor": None})


@app.post("/api/v1/hires/{employee_id}/conversations/{conversation_id}/messages")
def create_message(
    employee_id: str, conversation_id: str, body: MessageCreate, request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service),
):
    _hire(employee_id)
    key = _key(idempotency_key)
    scope, canonical = f"message:create:{conversation_id}", _canonical(body)
    try:
        replay = repo.check_idempotency(scope, key, canonical)
    except IdempotencyConflict:
        return safe_error(request, 409, "idempotency_conflict", "This idempotency key was already used with different input.")
    if replay:
        return safe_error(request, 409, "idempotent_replay_conflict", "The original message result already exists; read conversation history.")
    try:
        response = service.send_message(conversation_id, body.message)
    except MedicalContentRejected:
        return safe_error(request, 422, "medical_content_requires_certificate_check", "Use the dedicated Certificate Check; medical content was not saved.")
    except KeyError:
        return safe_error(request, 404, "conversation_not_found", "The conversation was not found.")
    assistant = repo.list_policy_messages(conversation_id)[-1]
    repo.save_idempotency(scope, key, canonical, target_type="policy_message", target_id=assistant["id"], target_version=None, http_status=200, outcome_code=response.type)
    conversation = repo.get_policy_conversation(conversation_id)
    return success(request, response.model_dump(mode="json"), simulated_date=conversation["simulated_date"])


@app.delete("/api/v1/hires/{employee_id}/conversations/{conversation_id}")
def delete_conversation(employee_id: str, conversation_id: str, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo)):
    _hire(employee_id); _key(idempotency_key)
    if not repo.delete_policy_conversation(conversation_id):
        return safe_error(request, 404, "conversation_not_found", "The conversation was not found.")
    return success(request, {"deleted": True})


@app.post("/api/v1/hires/{employee_id}/escalation-offers/{offer_id}/consent")
def consent_escalation(employee_id: str, offer_id: str, body: VersionAction, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), service: AishaService = Depends(get_service)):
    _hire(employee_id); _key(idempotency_key)
    try:
        return success(request, service.consent_escalation(offer_id, expected_version=body.expected_version), status=201)
    except KeyError:
        return safe_error(request, 404, "offer_not_found", "The escalation offer was not found.")
    except ValueError:
        return safe_error(request, 409, "stale_resource_version", "The escalation offer has changed.")


@app.get("/api/v1/hires/{employee_id}/profile")
def get_profile(employee_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id)
    return success(request, repo.get_hire_profile(employee_id).model_dump(mode="json"))


@app.post("/api/v1/hires/{employee_id}/attribute-change-requests")
def create_attribute_request(employee_id: str, body: AttributeCreate, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), service: AishaService = Depends(get_service)):
    _hire(employee_id); _key(idempotency_key)
    try:
        return success(request, service.request_attribute_change(employee_id, body.attribute_name, body.proposed_value, consent=body.consent), status=201)
    except ValueError:
        return safe_error(request, 422, "invalid_attribute_request", "The attribute request is invalid or lacks consent.")


@app.post("/api/v1/hr/attribute-change-requests/{request_id}/{action}")
def resolve_attribute_request(request_id: str, action: str, body: AttributeResolve, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), service: AishaService = Depends(get_service)):
    _key(idempotency_key)
    if action not in {"approve", "reject"}:
        return safe_error(request, 404, "action_not_found", "The HR action was not found.")
    try:
        data = service.resolve_attribute_request(request_id, approve=action == "approve", expected_version=body.expected_version, expected_profile_revision=body.expected_profile_revision, hr_user=body.hr_user)
        return success(request, data)
    except KeyError:
        return safe_error(request, 404, "attribute_request_not_found", "The request was not found.")
    except ValueError:
        return safe_error(request, 409, "stale_resource_version", "The request or Hire Profile has changed.")


@app.post("/api/v1/hires/{employee_id}/certificate-checks")
async def certificate_check(
    employee_id: str, request: Request,
    evaluation_date: date = Form(), acknowledged: bool = Form(), file: UploadFile = File(),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    service: AishaService = Depends(get_service),
):
    _hire(employee_id); _key(idempotency_key)
    data = await file.read(settings.certificate_max_bytes + 1)
    outcome = service.medical.check(data, filename=file.filename or "upload", evaluation_date=evaluation_date, applicability=ApplicabilityStatus.APPLIES, acknowledged=acknowledged)
    if outcome.kind == "upload_rejection":
        status = 413 if outcome.code == "file_too_large" else 415
        return safe_error(request, status, outcome.code or "upload_rejection", "The upload is outside the safe PDF/PNG/JPEG envelope.")
    if outcome.kind == "check_failure":
        return safe_error(request, 500, "certificate_check_failed", "Local certificate processing failed safely.", retryable=True)
    if outcome.kind == "privacy_acknowledgement_required":
        return safe_error(request, 422, "privacy_acknowledgement_required", "Acknowledge the local result-only privacy notice before processing.")
    return success(request, outcome.model_dump(mode="json"))


@app.get("/api/v1/hr/escalation-cases")
def hr_cases(request: Request, repo: Repo = Depends(get_repo)):
    return success(request, {"items": repo.list_escalation_cases(), "next_cursor": None})


@app.get("/api/v1/hr/validation-results")
def hr_validation_results(request: Request, repo: Repo = Depends(get_repo)):
    return success(request, {"items": repo.list_shared_validation_results(), "next_cursor": None})
