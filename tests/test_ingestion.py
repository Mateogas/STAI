from __future__ import annotations

import pytest

from stai.handbook import build_handbook
from stai.ingestion import (
    RetrievalBuildVerificationError,
    stage_handbook_build,
)
from stai.state import Repo


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
