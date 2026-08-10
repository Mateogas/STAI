import os
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from stai.state import MedicalContentRejected, Repo


def make_repo(tmp_path: Path) -> Repo:
    return Repo(tmp_path / "aisha.db", secret_path=tmp_path / "secrets" / "install.key")


def test_schema_pragmas_and_single_alyssa_seed(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert repo.schema_version == 2
    assert repo.get_hire_profile("emp-alyssa").role_key == "branch_banking_associate"
    assert repo.list_hire_ids() == ["emp-alyssa"]
    with sqlite3.connect(repo.db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0  # connection-local
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"hires", "hire_profiles", "policy_conversations", "validation_results", "active_retrieval_build"} <= tables


def test_connection_enables_required_runtime_pragmas(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    with repo.connection() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA secure_delete").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000


def test_installation_key_is_mode_0600_and_not_recreated_with_results(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    first = repo.ensure_installation_key()
    assert len(first) == 32
    assert oct(repo.secret_path.stat().st_mode & 0o777) == "0o600"
    repo.insert_test_validation_result("val-1")
    repo.secret_path.unlink()
    with pytest.raises(RuntimeError, match="certificate checking is disabled"):
        repo.ensure_installation_key()


def test_policy_conversation_rejects_medical_content_before_persistence(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    conversation = repo.create_policy_conversation("emp-alyssa", date(2026, 8, 10))
    repo.add_policy_message(conversation["id"], "hire", "When is the payroll cutoff?")
    with pytest.raises(MedicalContentRejected):
        repo.add_policy_message(conversation["id"], "hire", "Here is my diagnosis and medical certificate")
    assert [m["text"] for m in repo.list_policy_messages(conversation["id"])] == [
        "When is the payroll cutoff?"
    ]


def test_verified_retrieval_pointer_activation_and_rollback(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    repo.register_retrieval_build("build-a", "1.0", "manifest-a", "collection-a", verified=True)
    repo.activate_retrieval_build("build-a")
    repo.register_retrieval_build("build-b", "1.1", "manifest-b", "collection-b", verified=True)
    repo.activate_retrieval_build("build-b")
    assert repo.get_active_retrieval_build()["build_id"] == "build-b"
    assert repo.rollback_retrieval_build()["build_id"] == "build-a"
    assert repo.get_active_retrieval_build()["generation"] == 3


def test_full_demo_reset_is_transactional_and_rotates_key(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = repo.ensure_installation_key()
    conv = repo.create_policy_conversation("emp-alyssa", date(2026, 8, 10))
    repo.add_policy_message(conv["id"], "hire", "Payroll question")
    repo.put_holiday_cache(2026, [{"date": "2026-08-21", "name": "Synthetic Holiday"}])
    repo.insert_test_validation_result("val-reset")
    repo.full_demo_reset()
    assert repo.list_policy_messages(conv["id"]) == []
    assert repo.get_holiday_cache(2026) is None
    assert repo.count_validation_results() == 0
    assert repo.ensure_installation_key() != before
    assert repo.list_hire_ids() == ["emp-alyssa"]


def test_persistence_privacy_denylist_not_present_as_columns(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    forbidden = {"filename", "ocr_text", "diagnosis", "raw_error", "confidence_map", "document_bytes"}
    with sqlite3.connect(repo.db_path) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        columns = {r[1] for table in tables for r in conn.execute(f'PRAGMA table_info("{table}")')}
    assert not (columns & forbidden)

