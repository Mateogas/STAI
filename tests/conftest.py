from __future__ import annotations

import pytest

from stai.models import HireProfile
from stai.state import Repo


@pytest.fixture
def repo(tmp_path) -> Repo:
    """Repo on a throwaway normalized SQLite file."""
    return Repo(tmp_path / "test.db", secret_path=tmp_path / "install.key")


@pytest.fixture
def alyssa(repo) -> HireProfile:
    profile = repo.get_hire_profile("emp-alyssa")
    assert profile is not None
    return profile
