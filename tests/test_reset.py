from datetime import date

import pytest

from stai.state import Repo


def test_reset_failure_before_commit_preserves_product_state(tmp_path, monkeypatch) -> None:
    repo = Repo(tmp_path / "db.sqlite", secret_path=tmp_path / "install.key")
    conversation = repo.create_policy_conversation("emp-alyssa", date(2026, 8, 10))
    repo.add_policy_message(conversation["id"], "hire", "Keep this ordinary policy question")
    monkeypatch.setattr(repo, "_seed_policy_state", lambda _conn: (_ for _ in ()).throw(RuntimeError("seed failed")))
    with pytest.raises(RuntimeError, match="seed failed"):
        repo.full_demo_reset()
    assert repo.list_policy_messages(conversation["id"])[0]["text"].startswith("Keep this")
