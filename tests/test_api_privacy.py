from fastapi.testclient import TestClient

from stai.api import app, get_repo, get_service
from stai.handbook import build_handbook
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import Repo


def test_public_responses_exclude_internal_and_medical_fields(tmp_path):
    repo = Repo(tmp_path / "api.db", secret_path=tmp_path / "key")
    service = AishaService(repo, load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path))
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_service] = lambda: service
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/v1/hires/emp-alyssa/certificate-checks",
            headers={"Idempotency-Key": "upload-1"},
            data={"evaluation_date": "2026-08-10", "acknowledged": "true"},
            files={"file": ("private.zip", b"PK\x03\x04unsafe", "application/zip")},
        )
        assert response.status_code == 415
        serialized = response.text.lower()
        for forbidden in (
            "private.zip", "document_fingerprint", "ocr", "diagnosis", "traceback",
            "similarity", "snippet", "collection", "model_name",
        ):
            assert forbidden not in serialized
        assert response.json()["error"]["code"] == "unsupported_media_type"
    finally:
        app.dependency_overrides.clear()


def test_openapi_has_no_legacy_contract_or_internal_fields():
    schema = app.openapi()
    assert "/chat" not in schema["paths"] and "/health" not in schema["paths"]
    assert "/api/v1/health" in schema["paths"]
    serialized = str(schema).lower()
    for forbidden in ("plan_changed", "sourceout", "snippet", "guardrail_category"):
        assert forbidden not in serialized
