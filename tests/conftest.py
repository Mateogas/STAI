from __future__ import annotations

import pytest

from stai.models import Employee
from stai.state import Repo


@pytest.fixture
def repo(tmp_path) -> Repo:
    """Repo on a throwaway SQLite file, seeded from the real data files."""
    r = Repo(tmp_path / "test.db")
    r.seed_if_empty()
    return r


@pytest.fixture
def maya(repo) -> Employee:
    emp = repo.get_employee("emp-maya")
    assert emp is not None
    return emp
