"""Chroma retrieval with optional metadata filters (doc_type / department)."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from stai.config import settings
from stai.models import ApplicabilityStatus, HireProfile


@lru_cache(maxsize=1)
def get_vector_store():
    from langchain_chroma import Chroma
    from langchain_ollama import OllamaEmbeddings

    store = Chroma(
        collection_name=settings.collection_name,
        embedding_function=OllamaEmbeddings(
            model=settings.embed_model, base_url=settings.ollama_base_url
        ),
        persist_directory=str(settings.chroma_dir),
    )
    return store


def collection_count() -> int:
    return get_vector_store()._collection.count()


def retrieve(
    query: str,
    k: int | None = None,
    doc_type: str | None = None,
    department: str | None = None,
) -> list[Document]:
    """Top-k similarity search; empty list if the collection was never ingested."""
    store = get_vector_store()
    if collection_count() == 0:
        return []

    clauses = []
    if doc_type:
        clauses.append({"doc_type": {"$eq": doc_type}})
    if department:
        clauses.append({"department": {"$eq": department}})
    where = None
    if len(clauses) == 1:
        where = clauses[0]
    elif clauses:
        where = {"$and": clauses}

    return store.similarity_search(query, k=k or settings.retriever_k, filter=where)


def format_docs(docs: list[Document]) -> str:
    """Render retrieved chunks the way the agent is told to cite them."""
    blocks = []
    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        blocks.append(f"[source: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Immutable handbook-page retrieval


class KnowledgeIndexIntegrityError(RuntimeError):
    pass


class RetrievalOutcome(StrEnum):
    READY = "ready"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ATTRIBUTE_REQUIRED = "hire_attribute_required"
    POLICY_CONFLICT = "policy_conflict"
    INDEX_OUTAGE = "knowledge_index_outage"
    INTEGRITY_FAILURE = "integrity_failure"
    HANDBOOK_OMISSION = "handbook_omission"


class HandbookPageRecord(BaseModel):
    schema_version: int
    record_id: str
    handbook_version: str
    handbook_artifact_sha256: str
    page_manifest_sha256: str
    page: int = Field(ge=1)
    page_key: str
    page_content_sha256: str
    policy_id: str | None
    policy_revision: str | None
    title: str
    topic: str | None
    subareas: list[str]
    status: str
    effective_date: str | None
    supersedes: str | None = None
    page_kind: str
    procedure_id: str | None = None
    claim_types: list[str]
    applicability: dict[str, list[str]] | None
    route: str | None
    content: str


class RetrievedEvidence(BaseModel):
    record_id: str
    policy_id: str
    policy_revision: str
    handbook_version: str
    page: int
    page_kind: str
    content_sha256: str
    applicability: ApplicabilityStatus
    content: str = Field(exclude=True)


class PolicyRetrievalResult(BaseModel):
    outcome: RetrievalOutcome
    evidence: list[RetrievedEvidence] = Field(default_factory=list)
    required_attribute: str | None = None


def load_page_records(
    path: Path,
    *,
    expected_manifest: dict | None = None,
) -> list[HandbookPageRecord]:
    try:
        records = [HandbookPageRecord.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except Exception as exc:
        raise KnowledgeIndexIntegrityError("invalid handbook page records") from exc
    if not records or len({record.record_id for record in records}) != len(records):
        raise KnowledgeIndexIntegrityError("missing or duplicate record identity")
    for record in records:
        if hashlib.sha256(record.content.encode()).hexdigest() != record.page_content_sha256:
            raise KnowledgeIndexIntegrityError("page content hash mismatch")
        if expected_manifest:
            if record.handbook_version != expected_manifest["handbook_version"]:
                raise KnowledgeIndexIntegrityError("handbook version mismatch")
            if record.handbook_artifact_sha256 != expected_manifest["handbook_artifact_sha256"]:
                raise KnowledgeIndexIntegrityError("handbook artifact mismatch")
            if record.page_manifest_sha256 != expected_manifest["manifest_sha256"]:
                raise KnowledgeIndexIntegrityError("page manifest mismatch")
    return records


_TOKEN = re.compile(r"[a-z0-9-]+")
_PROFILE_FIELDS = {
    "role_keys": "role_key",
    "department_keys": "department_key",
    "employment_classifications": "employment_classification",
    "work_sites": "work_site",
}


def _applicability(record: HandbookPageRecord, profile: HireProfile) -> tuple[ApplicabilityStatus, str | None]:
    if not record.applicability:
        return ApplicabilityStatus.APPLIES, None
    for rule_key, profile_key in _PROFILE_FIELDS.items():
        allowed = record.applicability[rule_key]
        if allowed == ["all"]:
            continue
        actual = getattr(profile, profile_key, None)
        if actual is None:
            return ApplicabilityStatus.NEEDS_CLARIFICATION, profile_key
        if actual not in allowed:
            return ApplicabilityStatus.DOES_NOT_APPLY, None
    return ApplicabilityStatus.APPLIES, None


def hybrid_retrieve(
    query: str,
    profile: HireProfile,
    records: list[HandbookPageRecord],
    *,
    dense_record_ids: list[str] | None = None,
    k: int = 8,
    adjacent: bool = False,
) -> PolicyRetrievalResult:
    """Union deterministic lexical candidates with a supplied Chroma dense ranking."""
    query_tokens = set(_TOKEN.findall(query.lower()))
    exact_ids = {token.upper() for token in query_tokens if re.fullmatch(r"(?:pay|acc|hrp)-\d{3}", token)}
    dense_rank = {record_id: index for index, record_id in enumerate(dense_record_ids or [])}
    ranked: list[tuple[float, HandbookPageRecord]] = []
    for record in records:
        haystack = set(_TOKEN.findall(f"{record.policy_id or ''} {record.title} {record.content}".lower()))
        lexical = len(query_tokens & haystack) / max(1, len(query_tokens))
        if record.policy_id in exact_ids:
            lexical += 10
        dense = 1 / (1 + dense_rank[record.record_id]) if record.record_id in dense_rank else 0
        if lexical or dense:
            ranked.append((lexical + dense * 0.35, record))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].page))
    evidence: list[RetrievedEvidence] = []
    required: str | None = None
    selected_ids: set[str] = set()
    for _, record in ranked:
        if record.status != "active" or record.page_kind not in {"policy", "procedure"} or not record.policy_id:
            continue
        applicability, missing = _applicability(record, profile)
        if missing and required is None:
            required = missing
        if missing:
            continue
        if record.record_id in selected_ids:
            continue
        selected_ids.add(record.record_id)
        evidence.append(RetrievedEvidence(
            record_id=record.record_id,
            policy_id=record.policy_id,
            policy_revision=record.policy_revision or "1",
            handbook_version=record.handbook_version,
            page=record.page,
            page_kind=record.page_kind,
            content_sha256=record.page_content_sha256,
            applicability=applicability,
            content=record.content,
        ))
        if len(evidence) >= k:
            break
    if required:
        return PolicyRetrievalResult(outcome=RetrievalOutcome.ATTRIBUTE_REQUIRED, required_attribute=required)
    if not evidence:
        return PolicyRetrievalResult(outcome=RetrievalOutcome.INSUFFICIENT_EVIDENCE)
    return PolicyRetrievalResult(outcome=RetrievalOutcome.READY, evidence=evidence)
