from __future__ import annotations

import pytest

from stai.models import HireProfile
from stai.state import Repo


@pytest.fixture(autouse=True)
def offline_react_runtime(monkeypatch):
    """Keep the test suite offline while production requires LocalReactRunner."""
    from tests.fakes import OfflineReactRunner
    from stai.models import GuardrailVerdict

    class OfflineClassifier:
        def __call__(self, _message):
            return GuardrailVerdict(category="on_topic")

        def available(self):
            return True

    monkeypatch.setattr("stai.agent.LocalReactRunner", OfflineReactRunner)
    monkeypatch.setattr("stai.guardrails.LocalInputClassifier", OfflineClassifier)


@pytest.fixture
def repo(tmp_path) -> Repo:
    """Repo on a throwaway normalized SQLite file."""
    return Repo(tmp_path / "test.db", secret_path=tmp_path / "install.key")


@pytest.fixture
def alyssa(repo) -> HireProfile:
    profile = repo.get_hire_profile("emp-alyssa")
    assert profile is not None
    return profile
