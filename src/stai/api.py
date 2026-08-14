"""Typed, versioned REST contract shared with AISHA's Streamlit journeys."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import date
from functools import lru_cache
from typing import Annotated

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from stai.config import settings
from stai.handbook import build_handbook
from stai.medical import preflight_upload
from stai.models import ApplicabilityStatus
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import IdempotencyConflict, MedicalContentRejected, Repo

API_VERSION = "v1"
DISCLAIMER = (
    "AISHA is a fictional educational capstone prototype. It is not affiliated "
    "with, endorsed by, or representative of BDO Unibank."
)

app = FastAPI(title="AISHA - AI Support for Hires and Associates", description=DISCLAIMER, version="1.0.0")
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
    value = {"request_id": request.state.request_id, "api_version": API_VERSION}
    if simulated_date:
        value["simulated_date"] = simulated_date
    return value


def success(request: Request, data, *, status: int = 200, simulated_date: str | None = None):
    return JSONResponse(status_code=status, content={"data": data, "meta": _meta(request, simulated_date)})


def safe_error(request: Request, status: int, code: str, message: str, *, retryable: bool = False, fields: list[str] | None = None):
    return JSONResponse(status_code=status, content={
        "error": {"code": code, "message": message, "retryable": retryable, "fields": fields or []},
        "meta": _meta(request),
    })


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, _exc: RequestValidationError):
    return safe_error(request, 422, "invalid_request", "One or more request fields are invalid.")


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return safe_error(request, exc.status_code, detail.get("code", "request_failed"), detail.get("message", "The request could not be completed."))


@app.exception_handler(Exception)
async def unexpected_error(request: Request, _exc: Exception):
    return safe_error(request, 500, "unexpected_internal", "AISHA could not complete the request safely.", retryable=True)


@lru_cache(maxsize=1)
def get_repo() -> Repo:
    return Repo()


@lru_cache(maxsize=1)
def get_service() -> AishaService:
    artifacts = build_handbook()
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    records = load_page_records(artifacts.rag_pages_path, expected_manifest=manifest)
    from stai.retriever import ChromaHandbookIndex

    return AishaService(
        get_repo(),
        records,
        handbook_index=ChromaHandbookIndex(get_repo(), records),
        agent_enabled=settings.agent_enabled,
    )


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


def _check_replay(repo: Repo, scope: str, key: str, canonical: str, request: Request):
    try:
        return repo.check_idempotency(scope, key, canonical)
    except IdempotencyConflict:
        return safe_error(request, 409, "idempotency_conflict", "This idempotency key was already used with different input.")


def _save_replay(repo: Repo, scope: str, key: str, canonical: str, target_type: str, target_id: str, version: int | None, status: int, outcome: str) -> None:
    repo.save_idempotency(scope, key, canonical, target_type=target_type, target_id=target_id, target_version=version, http_status=status, outcome_code=outcome)


def _cursor_page(items: list[dict], cursor: str | None, limit: int, *, created_key: str, id_key: str) -> dict:
    if cursor:
        try:
            created, identity = json.loads(base64.urlsafe_b64decode(cursor + "===").decode())
            items = [item for item in items if (item[created_key], item[id_key]) < (created, identity)]
        except Exception:
            raise HTTPException(422, {"code": "invalid_cursor", "message": "The pagination cursor is invalid."})
    page = items[: limit + 1]
    next_cursor = None
    if len(page) > limit:
        page = page[:limit]
        last = page[-1]
        next_cursor = base64.urlsafe_b64encode(json.dumps([last[created_key], last[id_key]]).encode()).decode().rstrip("=")
    return {"items": page, "next_cursor": next_cursor}


def _public_policy_response(response) -> dict:
    payload = response.model_dump(mode="json")
    payload.pop("claims", None)
    return payload


def _public_validation_result(row: dict) -> dict:
    grouped = {name: [] for name in ("missing", "inconsistency", "warning", "human_review")}
    for item in row.get("codes", []):
        grouped[item["family"]].append(item["code"])
    return {
        "kind": "validation_result", "validation_id": row["validation_id"], "status": row["status"],
        "handbook_version": row["handbook_version"], "profile_revision": row["profile_revision"],
        "attempt_count": row["accepted_attempt_count"], "share_state": row["share_state"],
        "version": row["resource_version"], "missing_codes": grouped["missing"],
        "inconsistency_codes": grouped["inconsistency"], "warning_codes": grouped["warning"],
        "review_codes": grouped["human_review"], "citations": row.get("citations", []),
        "created_at_utc": row["created_at_utc"], "simulated_evaluation_date": row["simulated_evaluation_date"],
        "disclaimer": row["disclaimer"], "official_hr_document_route": row["official_hr_document_route"],
    }


class ConversationCreate(BaseModel):
    simulated_date: date


class MessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class VersionAction(BaseModel):
    expected_version: int = Field(ge=1)


class HrVersionAction(VersionAction):
    hr_user: str = Field(min_length=1, max_length=80)
    resolution_summary: str = Field(default="Resolved by HR.", min_length=1, max_length=2000)


class CaseMessageCreate(VersionAction):
    message: str = Field(min_length=1, max_length=4000)


class HrCaseMessageCreate(CaseMessageCreate):
    internal: bool = False


class AttributeCreate(BaseModel):
    attribute_name: str
    proposed_value: str
    consent: bool


class AttributeResolve(HrVersionAction):
    expected_profile_revision: int = Field(ge=1)


@app.get("/api/v1/health")
def health(
    request: Request,
    repo: Repo = Depends(get_repo),
    service: AishaService = Depends(get_service),
):
    try:
        active = repo.get_active_retrieval_build()
        sqlite_state = "ready"
    except Exception:
        active, sqlite_state = None, "unavailable"
    index_state = service.handbook_index.runtime_status()
    runner = service.turn_engine.agent_runner
    agent_state = "ready" if runner and getattr(runner, "available", lambda: False)() else "degraded"
    classifier = service.turn_engine.input_classifier
    guardrail_state = "ready" if classifier and getattr(classifier, "available", lambda: False)() else "degraded"
    if sqlite_state == "unavailable":
        status, code = "unavailable", 503
    elif index_state != "ready" or agent_state != "ready" or guardrail_state != "ready":
        status, code = "degraded", 200
    else:
        status, code = "ready", 200
    return success(request, {
        "status": status, "sqlite": sqlite_state, "knowledge_index": index_state,
        "active_handbook_version": active["handbook_version"] if active else "1.0",
        "agent_model": agent_state, "guardrail_model": guardrail_state, "nager": "unknown",
        "disclaimer": DISCLAIMER,
    }, status=code)


@app.post("/api/v1/hires/{employee_id}/conversations")
def create_conversation(employee_id: str, body: ConversationCreate, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    _hire(employee_id); key = _key(idempotency_key)
    scope, canonical = f"conversation:create:{employee_id}", _canonical(body)
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay:
        row = repo.get_policy_conversation(replay["target_resource_id"])
        return success(request, {"id": row["conversation_id"], "employee_id": row["hire_id"], "simulated_date": row["simulated_date"], "version": row["resource_version"]}, status=201, simulated_date=row["simulated_date"])
    data = service.create_conversation(employee_id, body.simulated_date)
    _save_replay(repo, scope, key, canonical, "conversation", data["id"], 1, 201, "created")
    return success(request, data, status=201, simulated_date=data["simulated_date"])


@app.get("/api/v1/hires/{employee_id}/conversations")
def list_conversations(employee_id: str, request: Request, cursor: str | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 20, repo: Repo = Depends(get_repo)):
    _hire(employee_id)
    rows = repo.list_policy_conversations(employee_id)
    return success(request, _cursor_page(rows, cursor, limit, created_key="created_at_utc", id_key="conversation_id"))


@app.get("/api/v1/hires/{employee_id}/conversations/{conversation_id}")
def get_conversation(employee_id: str, conversation_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id); row = repo.get_policy_conversation(conversation_id)
    if not row or row["hire_id"] != employee_id:
        return safe_error(request, 404, "conversation_not_found", "The conversation was not found.")
    return success(request, {"id": row["conversation_id"], "employee_id": row["hire_id"], "simulated_date": row["simulated_date"], "version": row["resource_version"]}, simulated_date=row["simulated_date"])


@app.get("/api/v1/hires/{employee_id}/conversations/{conversation_id}/messages")
def list_messages(employee_id: str, conversation_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id); conversation = repo.get_policy_conversation(conversation_id)
    if not conversation or conversation["hire_id"] != employee_id:
        return safe_error(request, 404, "conversation_not_found", "The conversation was not found.")
    return success(request, {"items": repo.list_policy_messages(conversation_id), "next_cursor": None})


@app.post("/api/v1/hires/{employee_id}/conversations/{conversation_id}/messages")
def create_message(employee_id: str, conversation_id: str, body: MessageCreate, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    _hire(employee_id); key = _key(idempotency_key)
    scope, canonical = f"message:create:{conversation_id}", _canonical(body)
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay:
        if replay["target_resource_type"] == "policy_message":
            payload = repo.get_policy_response_payload(replay["target_resource_id"])
        else:
            offer = repo.get_escalation_offer(replay["target_resource_id"])
            payload = offer
        if payload:
            payload.pop("claims", None)
        conversation = repo.get_policy_conversation(conversation_id)
        return success(request, payload, simulated_date=conversation["simulated_date"])
    try:
        response = service.send_message(conversation_id, body.message)
    except MedicalContentRejected:
        return safe_error(request, 422, "medical_content_requires_certificate_check", "Use the dedicated Certificate Check; medical content was not saved.")
    except KeyError:
        return safe_error(request, 404, "conversation_not_found", "The conversation was not found.")
    assistant = repo.list_policy_messages(conversation_id)[-1]
    target_type, target_id = "policy_message", assistant["id"]
    _save_replay(repo, scope, key, canonical, target_type, target_id, 1, 200, response.type)
    conversation = repo.get_policy_conversation(conversation_id)
    return success(request, _public_policy_response(response), simulated_date=conversation["simulated_date"])


@app.delete("/api/v1/hires/{employee_id}/conversations/{conversation_id}")
def delete_conversation(employee_id: str, conversation_id: str, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo)):
    _hire(employee_id); key = _key(idempotency_key); scope = f"conversation:delete:{conversation_id}"; canonical = "{}"
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, {"deleted": True})
    if not repo.delete_policy_conversation(conversation_id):
        return safe_error(request, 404, "conversation_not_found", "The conversation was not found.")
    _save_replay(repo, scope, key, canonical, "conversation", conversation_id, None, 200, "deleted")
    return success(request, {"deleted": True})


@app.post("/api/v1/hires/{employee_id}/escalation-offers/{offer_id}/consent")
def consent_escalation(employee_id: str, offer_id: str, body: VersionAction, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    _hire(employee_id); key = _key(idempotency_key); scope, canonical = f"offer:consent:{offer_id}", _canonical(body)
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, repo.get_escalation_case(replay["target_resource_id"]), status=201)
    try: data = service.consent_escalation(offer_id, expected_version=body.expected_version)
    except KeyError: return safe_error(request, 404, "offer_not_found", "The escalation offer was not found.")
    except ValueError: return safe_error(request, 409, "stale_resource_version", "The escalation offer has changed.")
    _save_replay(repo, scope, key, canonical, "escalation_case", data["case_id"], 1, 201, "created")
    return success(request, data, status=201)


@app.get("/api/v1/hires/{employee_id}/escalation-cases")
def hire_cases(employee_id: str, request: Request, service: AishaService = Depends(get_service)):
    _hire(employee_id); items = service.list_cases()
    return success(request, {"items": items, "next_cursor": None})


@app.get("/api/v1/hires/{employee_id}/conversations/{conversation_id}/escalation-cases")
def conversation_cases(employee_id: str, conversation_id: str, request: Request, service: AishaService = Depends(get_service)):
    _hire(employee_id)
    return success(request, {"items": service.list_cases(parent_conversation_id=conversation_id), "next_cursor": None})


@app.get("/api/v1/hires/{employee_id}/escalation-cases/{case_id}")
def hire_case(employee_id: str, case_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id); item = repo.get_escalation_case(case_id)
    if not item or item["hire_id"] != employee_id: return safe_error(request, 404, "case_not_found", "The escalation case was not found.")
    return success(request, item)


@app.get("/api/v1/hires/{employee_id}/escalation-cases/{case_id}/messages")
def hire_case_messages(employee_id: str, case_id: str, request: Request, service: AishaService = Depends(get_service)):
    _hire(employee_id)
    try: thread = service.get_case_thread(case_id)
    except (KeyError, PermissionError): return safe_error(request, 404, "case_not_found", "The escalation case was not found.")
    return success(request, thread)


@app.post("/api/v1/hires/{employee_id}/escalation-cases/{case_id}/messages")
def create_hire_case_message(employee_id: str, case_id: str, body: CaseMessageCreate, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), service: AishaService = Depends(get_service)):
    _hire(employee_id); key = _key(idempotency_key); scope, canonical = f"case:hire-message:{case_id}", _canonical(body)
    replay = _check_replay(service.repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, service.get_case_thread(case_id))
    try:
        thread = service.post_case_message(case_id, body.message, expected_version=body.expected_version)
    except KeyError: return safe_error(request, 404, "case_not_found", "The escalation case was not found.")
    except (ValueError, PermissionError): return safe_error(request, 409, "case_message_rejected", "The case changed or the message is not allowed.")
    version = thread["case"]["resource_version"]
    _save_replay(service.repo, scope, key, canonical, "escalation_case", case_id, version, 201, "case_message_added")
    return success(request, thread, status=201)


@app.get("/api/v1/hr/escalation-cases")
def hr_cases(request: Request, service: AishaService = Depends(get_service)):
    return success(request, {"items": service.list_cases(hr=True), "next_cursor": None})


@app.get("/api/v1/hr/escalation-cases/{case_id}")
def hr_case(case_id: str, request: Request, repo: Repo = Depends(get_repo)):
    item = repo.get_escalation_case(case_id)
    return success(request, item) if item else safe_error(request, 404, "case_not_found", "The escalation case was not found.")


@app.get("/api/v1/hr/escalation-cases/{case_id}/messages")
def hr_case_messages(case_id: str, request: Request, service: AishaService = Depends(get_service)):
    try: thread = service.get_case_thread(case_id, hr=True)
    except KeyError: return safe_error(request, 404, "case_not_found", "The escalation case was not found.")
    return success(request, thread)


@app.post("/api/v1/hr/escalation-cases/{case_id}/messages")
def create_hr_case_message(case_id: str, body: HrCaseMessageCreate, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), service: AishaService = Depends(get_service)):
    key = _key(idempotency_key); scope, canonical = f"case:hr-message:{case_id}", _canonical(body)
    replay = _check_replay(service.repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, service.get_case_thread(case_id, hr=True))
    try:
        thread = service.post_case_message(
            case_id, body.message, expected_version=body.expected_version,
            hr=True, internal=body.internal,
        )
    except KeyError: return safe_error(request, 404, "case_not_found", "The escalation case was not found.")
    except (ValueError, PermissionError): return safe_error(request, 409, "case_message_rejected", "The case changed or the message is not allowed.")
    version = thread["case"]["resource_version"]
    _save_replay(service.repo, scope, key, canonical, "escalation_case", case_id, version, 201, "case_message_added")
    return success(request, thread, status=201)


@app.post("/api/v1/hr/escalation-cases/{case_id}/close")
def close_hr_case(case_id: str, body: HrVersionAction, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo)):
    key = _key(idempotency_key); scope, canonical = f"case:close:{case_id}", _canonical(body)
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, repo.get_escalation_case(case_id))
    try: item = repo.close_escalation_case(case_id, expected_version=body.expected_version, hr_user=body.hr_user, resolution_summary=body.resolution_summary)
    except KeyError: return safe_error(request, 404, "case_not_found", "The escalation case was not found.")
    except ValueError: return safe_error(request, 409, "stale_resource_version", "The escalation case has changed.")
    _save_replay(repo, scope, key, canonical, "escalation_case", case_id, item["resource_version"], 200, "closed")
    return success(request, item)


@app.get("/api/v1/hires/{employee_id}/profile")
def get_profile(employee_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id); return success(request, repo.get_hire_profile(employee_id).model_dump(mode="json"))


@app.post("/api/v1/hires/{employee_id}/attribute-change-requests")
def create_attribute_request(employee_id: str, body: AttributeCreate, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    _hire(employee_id); key = _key(idempotency_key); scope, canonical = f"attribute:create:{employee_id}", _canonical(body)
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, repo.get_attribute_change_request(replay["target_resource_id"]), status=201)
    try: data = service.request_attribute_change(employee_id, body.attribute_name, body.proposed_value, consent=body.consent)
    except ValueError: return safe_error(request, 422, "invalid_attribute_request", "The attribute request is invalid or lacks consent.")
    _save_replay(repo, scope, key, canonical, "attribute_change_request", data["request_id"], 1, 201, "created")
    return success(request, data, status=201)


@app.get("/api/v1/hires/{employee_id}/attribute-change-requests")
def list_hire_attribute_requests(employee_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id); return success(request, {"items": repo.list_attribute_change_requests(employee_id), "next_cursor": None})


@app.get("/api/v1/hires/{employee_id}/attribute-change-requests/{request_id}")
def get_hire_attribute_request(employee_id: str, request_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id); item = repo.get_attribute_change_request(request_id)
    if not item or item["hire_id"] != employee_id: return safe_error(request, 404, "attribute_request_not_found", "The request was not found.")
    return success(request, item)


@app.get("/api/v1/hr/attribute-change-requests")
def list_hr_attribute_requests(request: Request, repo: Repo = Depends(get_repo)):
    return success(request, {"items": repo.list_attribute_change_requests(), "next_cursor": None})


@app.get("/api/v1/hr/attribute-change-requests/{request_id}")
def get_hr_attribute_request(request_id: str, request: Request, repo: Repo = Depends(get_repo)):
    item = repo.get_attribute_change_request(request_id)
    return success(request, item) if item else safe_error(request, 404, "attribute_request_not_found", "The request was not found.")


@app.post("/api/v1/hr/attribute-change-requests/{request_id}/{action}")
def resolve_attribute_request(request_id: str, action: str, body: AttributeResolve, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    key = _key(idempotency_key)
    if action not in {"approve", "reject"}: return safe_error(request, 404, "action_not_found", "The HR action was not found.")
    scope, canonical = f"attribute:{action}:{request_id}", _canonical(body)
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, repo.get_attribute_change_request(request_id))
    try: data = service.resolve_attribute_request(request_id, approve=action == "approve", expected_version=body.expected_version, expected_profile_revision=body.expected_profile_revision, hr_user=body.hr_user)
    except KeyError: return safe_error(request, 404, "attribute_request_not_found", "The request was not found.")
    except ValueError: return safe_error(request, 409, "stale_resource_version", "The request or Hire Profile has changed.")
    _save_replay(repo, scope, key, canonical, "attribute_change_request", request_id, data["version"], 200, data["status"])
    return success(request, data)


def _upload_error(request: Request, code: str):
    status = 413 if code == "file_too_large" else 415 if code in {"unsupported_media_type", "extension_content_mismatch"} else 422
    return safe_error(request, status, code, "The upload is outside the safe PDF/PNG/JPEG envelope.")


@app.post("/api/v1/hires/{employee_id}/certificate-checks")
async def certificate_check(employee_id: str, request: Request, evaluation_date: date = Form(), acknowledged: bool = Form(), file: UploadFile = File(), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    _hire(employee_id); key = _key(idempotency_key); data = await file.read(settings.certificate_max_bytes + 1)
    canonical = _canonical({"evaluation_date": evaluation_date.isoformat(), "acknowledged": acknowledged, "content_digest": hashlib.sha256(data).hexdigest()})
    scope = f"certificate:create:{employee_id}"
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, _public_validation_result(repo.get_validation_result(replay["target_resource_id"])))
    outcome = service.medical.check(data, filename=file.filename or "upload", evaluation_date=evaluation_date, applicability=ApplicabilityStatus.APPLIES, acknowledged=acknowledged)
    if outcome.kind == "upload_rejection": return _upload_error(request, outcome.code or "upload_rejection")
    if outcome.kind == "check_failure": return safe_error(request, 500, "certificate_check_failed", "Local certificate processing failed safely.", retryable=True)
    if outcome.kind == "privacy_acknowledgement_required": return safe_error(request, 422, "privacy_acknowledgement_required", "Acknowledge the local result-only privacy notice before processing.")
    if outcome.validation_id:
        _save_replay(repo, scope, key, canonical, "validation_result", outcome.validation_id, outcome.version, 200, outcome.kind)
        return success(request, _public_validation_result(repo.get_validation_result(outcome.validation_id)))
    return success(request, outcome.model_dump(mode="json"))


@app.post("/api/v1/hires/{employee_id}/certificate-checks/retry")
async def retry_certificate_check(employee_id: str, request: Request, retry_token: str = Form(), evaluation_date: date = Form(), file: UploadFile = File(), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    _hire(employee_id); key = _key(idempotency_key); data = await file.read(settings.certificate_max_bytes + 1)
    preflight = preflight_upload(data, file.filename or "upload")
    if not preflight.accepted: return _upload_error(request, preflight.code or "upload_rejection")
    canonical = _canonical({"token": retry_token, "evaluation_date": evaluation_date.isoformat(), "content_digest": hashlib.sha256(data).hexdigest()})
    scope = f"certificate:retry:{employee_id}"
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, _public_validation_result(repo.get_validation_result(replay["target_resource_id"])))
    try: repo.consume_retry_session(retry_token)
    except KeyError: return safe_error(request, 409, "retry_token_invalid_or_expired", "The certificate retry token is invalid or expired.")
    outcome = service.medical.check(data, filename=file.filename or "upload", evaluation_date=evaluation_date, applicability=ApplicabilityStatus.APPLIES, acknowledged=True, retry_used=True)
    if outcome.kind == "check_failure": return safe_error(request, 500, "certificate_check_failed", "Local certificate processing failed safely.", retryable=True)
    if outcome.validation_id:
        _save_replay(repo, scope, key, canonical, "validation_result", outcome.validation_id, outcome.version, 200, outcome.kind)
        return success(request, _public_validation_result(repo.get_validation_result(outcome.validation_id)))
    return success(request, outcome.model_dump(mode="json"))


@app.get("/api/v1/hires/{employee_id}/validation-results")
def list_hire_results(employee_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id); return success(request, {"items": repo.list_validation_results(employee_id), "next_cursor": None})


@app.get("/api/v1/hires/{employee_id}/validation-results/{validation_id}")
def get_hire_result(employee_id: str, validation_id: str, request: Request, repo: Repo = Depends(get_repo)):
    _hire(employee_id); item = repo.get_validation_result(validation_id)
    if not item or item["hire_id"] != employee_id: return safe_error(request, 404, "validation_result_not_found", "The Validation Result was not found.")
    return success(request, item)


def _result_share_action(employee_id: str, validation_id: str, body: VersionAction, request: Request, key_value: str | None, share: bool, repo: Repo, service: AishaService):
    _hire(employee_id); key = _key(key_value); action = "share" if share else "revoke"; scope, canonical = f"validation:{action}:{validation_id}", _canonical(body)
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, repo.get_validation_result(validation_id))
    try: service.share_validation_result(validation_id, expected_version=body.expected_version) if share else service.revoke_validation_result(validation_id, expected_version=body.expected_version)
    except KeyError: return safe_error(request, 404, "validation_result_not_found", "The Validation Result was not found.")
    except ValueError: return safe_error(request, 409, "stale_resource_version", "The Validation Result has changed.")
    item = repo.get_validation_result(validation_id); _save_replay(repo, scope, key, canonical, "validation_result", validation_id, item["resource_version"], 200, action)
    return success(request, item)


@app.post("/api/v1/hires/{employee_id}/validation-results/{validation_id}/share")
def share_result(employee_id: str, validation_id: str, body: VersionAction, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    return _result_share_action(employee_id, validation_id, body, request, idempotency_key, True, repo, service)


@app.post("/api/v1/hires/{employee_id}/validation-results/{validation_id}/revoke")
def revoke_result(employee_id: str, validation_id: str, body: VersionAction, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    return _result_share_action(employee_id, validation_id, body, request, idempotency_key, False, repo, service)


@app.delete("/api/v1/hires/{employee_id}/validation-results/{validation_id}")
def delete_result(employee_id: str, validation_id: str, request: Request, body: Annotated[VersionAction, Body()], idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), repo: Repo = Depends(get_repo), service: AishaService = Depends(get_service)):
    _hire(employee_id); key = _key(idempotency_key); scope, canonical = f"validation:delete:{validation_id}", _canonical(body)
    replay = _check_replay(repo, scope, key, canonical, request)
    if isinstance(replay, JSONResponse): return replay
    if replay: return success(request, {"deleted": True})
    try: deleted = service.delete_validation_result(validation_id, expected_version=body.expected_version)
    except ValueError: return safe_error(request, 409, "stale_resource_version", "The Validation Result has changed.")
    if not deleted: return safe_error(request, 404, "validation_result_not_found", "The Validation Result was not found.")
    _save_replay(repo, scope, key, canonical, "validation_result", validation_id, None, 200, "deleted")
    return success(request, {"deleted": True})


@app.get("/api/v1/hr/validation-results")
def hr_validation_results(request: Request, repo: Repo = Depends(get_repo)):
    return success(request, {"items": repo.list_shared_validation_results(), "next_cursor": None})


@app.get("/api/v1/hr/validation-results/{validation_id}")
def hr_validation_result(validation_id: str, request: Request, repo: Repo = Depends(get_repo)):
    item = repo.get_validation_result(validation_id)
    if not item or item["share_state"] != "shared": return safe_error(request, 404, "validation_result_not_found", "The shared Validation Result was not found.")
    return success(request, item)
