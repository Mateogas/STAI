"""Immutable active-edition handbook-page retrieval."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from stai.models import ApplicabilityStatus, HireProfile


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
    source_register_sha256: str | None = None
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
            if record.source_register_sha256 != expected_manifest.get("source_register_sha256"):
                raise KnowledgeIndexIntegrityError("source register mismatch")
    return records


_TOKEN = re.compile(r"[a-z0-9-]+")
_STOPWORDS = {
    "a", "about", "am", "an", "and", "are", "can", "could", "do", "does",
    "for", "how", "i", "in", "is", "it", "me", "my", "of", "on", "please",
    "the", "then", "this", "to", "want", "well", "what", "whats", "with",
    "work", "would", "you",
}
_EXPANSIONS = {
    "onboard": {"onboarding", "enrollment", "details", "records", "route"},
    "onboarding": {"enrollment", "details", "records", "route"},
    "put": {"change", "details", "corrections", "route"},
    "update": {"change", "details", "corrections", "route"},
    "help": {"support", "route"},
    "salary": {"payroll", "pay"},
    "wage": {"payroll", "pay"},
    "login": {"sign-in", "account", "access"},
    "clothes": {"clothing", "attire", "dress", "uniform"},
    "clothing": {"clothes", "attire", "dress", "uniform"},
    "attire": {"clothes", "clothing", "dress", "uniform"},
    "uniform": {"clothes", "clothing", "attire", "dress"},
}
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
    topic: str | None = None,
    policy_ids: set[str] | None = None,
) -> PolicyRetrievalResult:
    """Fuse weighted lexical and supplied dense candidates, then apply hard gates."""
    raw_tokens = set(_TOKEN.findall(query.lower()))
    exact_ids = {token.upper() for token in raw_tokens if re.fullmatch(r"(?:pay|acc|hrp)-\d{3}", token)}
    query_tokens = {token for token in raw_tokens if token not in _STOPWORDS}
    for token in tuple(query_tokens):
        query_tokens.update(_EXPANSIONS.get(token, set()))
    dense_rank = {record_id: index for index, record_id in enumerate(dense_record_ids or [])}
    ranked: list[tuple[float, HandbookPageRecord]] = []
    for record in records:
        if topic and record.topic != topic:
            continue
        title_tokens = set(_TOKEN.findall(record.title.lower()))
        body_tokens = set(_TOKEN.findall(record.content.lower()))
        subarea_tokens = set(_TOKEN.findall(" ".join(record.subareas).replace("_", " ").lower()))
        lexical = (
            len(query_tokens & title_tokens) * 4.0
            + len(query_tokens & subarea_tokens) * 5.0
            + len(query_tokens & body_tokens) * 1.25
        )
        if record.policy_id in exact_ids:
            lexical += 100.0
        if policy_ids and record.policy_id in policy_ids:
            lexical += 8.0
        if "payroll" in query_tokens and "details" in query_tokens and "payroll details" in record.title.lower():
            lexical += 12.0
        if (
            "payroll" in query_tokens
            and query_tokens & {"view", "download", "see"}
            and "payslip" in subarea_tokens
        ):
            lexical += 16.0
        if (
            query_tokens & {"clothes", "clothing", "attire", "uniform", "dress"}
            and "dress" in subarea_tokens
        ):
            lexical += 12.0
        dense = 1 / (1 + dense_rank[record.record_id]) if record.record_id in dense_rank else 0
        if lexical >= 1.0 or dense:
            ranked.append((lexical + dense * 3.0, record))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].page))
    evidence: list[RetrievedEvidence] = []
    selected_ids: set[str] = set()
    for _score, record in ranked:
        if record.status != "active" or record.page_kind not in {"policy", "procedure"} or not record.policy_id:
            continue
        applicability, missing = _applicability(record, profile)
        if missing:
            if not evidence:
                return PolicyRetrievalResult(
                    outcome=RetrievalOutcome.ATTRIBUTE_REQUIRED,
                    required_attribute=missing,
                )
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
    if not evidence:
        return PolicyRetrievalResult(outcome=RetrievalOutcome.INSUFFICIENT_EVIDENCE)
    return PolicyRetrievalResult(outcome=RetrievalOutcome.READY, evidence=evidence)


class HandbookIndex(Protocol):
    """Internal retrieval seam used by the turn module and its tests."""

    def search(
        self,
        query: str,
        profile: HireProfile,
        *,
        topic: str | None = None,
        policy_ids: set[str] | None = None,
        k: int = 8,
    ) -> PolicyRetrievalResult: ...


class InMemoryHandbookIndex:
    """Verified-record adapter used explicitly by deterministic unit tests."""

    def __init__(self, records: list[HandbookPageRecord]) -> None:
        self.records = records

    def search(
        self,
        query: str,
        profile: HireProfile,
        *,
        topic: str | None = None,
        policy_ids: set[str] | None = None,
        k: int = 8,
    ) -> PolicyRetrievalResult:
        return hybrid_retrieve(
            query,
            profile,
            self.records,
            topic=topic,
            policy_ids=policy_ids,
            k=k,
        )

    def runtime_status(self) -> str:
        return "degraded"


class ChromaHandbookIndex(InMemoryHandbookIndex):
    """Required active-build Chroma adapter; retrieval failures are surfaced."""

    def __init__(self, repo, records: list[HandbookPageRecord], *, dense_lookup=None) -> None:
        super().__init__(records)
        self.repo = repo
        self.dense_lookup = dense_lookup
        self.last_search_mode = "degraded"

    def runtime_status(self) -> str:
        try:
            import httpx
            from langchain_chroma import Chroma

            from stai.config import settings

            active = self.repo.get_active_retrieval_build()
            if not active:
                return "degraded"
            expected = self.records[0]
            if (
                active["handbook_version"] != expected.handbook_version
                or active["manifest_identity"] != expected.page_manifest_sha256
            ):
                return "degraded"
            store = Chroma(
                collection_name=active["collection_name"],
                persist_directory=str(settings.chroma_dir),
            )
            if store._collection.count() != len(self.records):
                return "degraded"
            response = httpx.get(
                f"{settings.ollama_base_url.rstrip('/')}/api/tags",
                timeout=settings.agent_probe_timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
            names = {
                str(item.get("name", "")).split(":latest")[0]
                for item in response.json().get("models", [])
            }
            return "ready" if settings.embed_model.split(":latest")[0] in names else "degraded"
        except Exception:
            return "unavailable"

    def search(
        self,
        query: str,
        profile: HireProfile,
        *,
        topic: str | None = None,
        policy_ids: set[str] | None = None,
        k: int = 8,
    ) -> PolicyRetrievalResult:
        dense_record_ids: list[str] = []
        try:
            if self.dense_lookup:
                dense_record_ids = list(self.dense_lookup(query, max(k * 3, 12)))
                self.last_search_mode = "active_chroma"
                return hybrid_retrieve(
                    query,
                    profile,
                    self.records,
                    dense_record_ids=dense_record_ids,
                    topic=topic,
                    policy_ids=policy_ids,
                    k=k,
                )
            from langchain_chroma import Chroma

            from stai.config import settings
            from stai.ollama_runtime import build_embeddings

            active = self.repo.get_active_retrieval_build()
            if not active:
                raise RuntimeError("no active retrieval build")
            expected = self.records[0]
            if (
                active["handbook_version"] != expected.handbook_version
                or active["manifest_identity"] != expected.page_manifest_sha256
            ):
                raise RuntimeError("active retrieval identity does not match verified records")
            store = Chroma(
                collection_name=active["collection_name"],
                embedding_function=build_embeddings(),
                persist_directory=str(settings.chroma_dir),
            )
            documents = store.similarity_search(query, k=max(k * 3, 12))
            dense_record_ids = [
                str(document.metadata.get("record_id"))
                for document in documents
                if document.metadata.get("record_id")
            ]
            self.last_search_mode = "active_chroma"
        except Exception as exc:
            self.last_search_mode = "unavailable"
            raise KnowledgeIndexIntegrityError("active Chroma retrieval failed") from exc
        return hybrid_retrieve(
            query,
            profile,
            self.records,
            dense_record_ids=dense_record_ids,
            topic=topic,
            policy_ids=policy_ids,
            k=k,
        )
