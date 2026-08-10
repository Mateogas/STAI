from __future__ import annotations

import pytest

from stai.config import settings
from stai.handbook import build_handbook
from stai.ingestion import (
    RetrievalBuildVerificationError,
    load_documents,
    parse_front_matter,
    split_documents,
    stage_handbook_build,
)
from stai.state import Repo


def test_parse_front_matter():
    meta, body = parse_front_matter("---\ntitle: X\ndoc_type: policy\n---\n\n# Hello\n")
    assert meta == {"title": "X", "doc_type": "policy"}
    assert body.strip() == "# Hello"


def test_parse_front_matter_absent():
    meta, body = parse_front_matter("# Just markdown\n")
    assert meta == {} and body.startswith("# Just")


def test_load_documents_carries_metadata():
    docs = load_documents()
    assert len(docs) == 10
    by_source = {d.metadata["source"]: d for d in docs}
    assert "leave_policy.md" in by_source
    assert by_source["leave_policy.md"].metadata["doc_type"] == "policy"
    assert by_source["payslip_explainer.md"].metadata["doc_type"] == "explainer"
    assert all(d.metadata["department"] for d in docs)
    assert all("---" not in d.page_content[:10] for d in docs)  # front matter stripped


def test_split_documents_chunks_and_preserves_metadata():
    docs = load_documents()
    chunks = split_documents(docs)
    assert len(chunks) > len(docs)
    assert all(len(c.page_content) <= settings.chunk_size + 200 for c in chunks)
    assert all("source" in c.metadata and "doc_type" in c.metadata for c in chunks)


def test_staged_build_activates_only_after_vector_verification(tmp_path):
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    artifacts = build_handbook(tmp_path / "handbook")
    staged = stage_handbook_build(
        repo,
        artifacts,
        vector_builder=lambda collection, records: {"count": len(records), "dimension": 768},
    )
    assert staged["record_count"] == 108
    assert repo.get_active_retrieval_build()["build_id"] == staged["build_id"]


def test_failed_partial_build_leaves_active_pointer_untouched(tmp_path):
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    artifacts = build_handbook(tmp_path / "handbook")
    first = stage_handbook_build(repo, artifacts, vector_builder=lambda _c, rows: {"count": len(rows), "dimension": 768})
    with pytest.raises(RetrievalBuildVerificationError):
        stage_handbook_build(repo, artifacts, vector_builder=lambda _c, rows: {"count": len(rows) - 1, "dimension": 768}, build_salt="partial")
    assert repo.get_active_retrieval_build()["build_id"] == first["build_id"]
