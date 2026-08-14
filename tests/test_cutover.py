import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from stai.state import Repo, cutover_legacy_database


def test_cutover_replaces_legacy_only_after_verified_builder(tmp_path: Path) -> None:
    db = tmp_path / "stai.db"
    with closing(sqlite3.connect(db)) as conn:
        with conn:
            conn.execute("CREATE TABLE legacy_pulse(raw_reply TEXT)")
    cutover_legacy_database(db, verifier=lambda repo: repo.schema_version == 7)
    repo = Repo(db, secret_path=tmp_path / "install.key")
    assert repo.schema_version == 7
    with closing(sqlite3.connect(db)) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "legacy_pulse" not in tables


def test_failed_cutover_keeps_legacy_file_untouched(tmp_path: Path) -> None:
    db = tmp_path / "stai.db"
    with closing(sqlite3.connect(db)) as conn:
        with conn:
            conn.execute("CREATE TABLE legacy_marker(value TEXT)")
            conn.execute("INSERT INTO legacy_marker VALUES ('keep-me')")
    before = db.read_bytes()
    with pytest.raises(RuntimeError):
        cutover_legacy_database(db, verifier=lambda _repo: False)
    assert db.read_bytes() == before
