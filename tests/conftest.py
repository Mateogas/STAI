from __future__ import annotations

import pytest

from stai.config import settings
from stai.models import HireProfile
from stai.state import Repo


@pytest.fixture(autouse=True)
def offline_react_runtime(monkeypatch, tmp_path, request):
    """Keep tests isolated while production requires Ollama and active Chroma.

    Tests marked ``live`` opt out of this offline seam entirely: they build a
    real service against a real Ollama endpoint and manage their own isolation.
    """
    if request.node.get_closest_marker("live"):
        return
    from tests.fakes import OfflineReactRunner
    from stai.models import GuardrailVerdict
    from stai.retriever import InMemoryHandbookIndex

    class OfflineHandbookIndex(InMemoryHandbookIndex):
        def __init__(self, _repo, records, **_kwargs):
            super().__init__(records)

    class OfflineClassifier:
        def __call__(self, _message):
            return GuardrailVerdict(category="on_topic")

        def available(self):
            return True

    monkeypatch.setattr("stai.agent.LocalReactRunner", OfflineReactRunner)
    monkeypatch.setattr("stai.guardrails.LocalInputClassifier", OfflineClassifier)
    monkeypatch.setattr("stai.retriever.ChromaHandbookIndex", OfflineHandbookIndex)
    monkeypatch.setattr(settings, "db_path", tmp_path / "app.db")
    monkeypatch.setattr(settings, "chroma_dir", tmp_path / "chroma")


@pytest.fixture
def repo(tmp_path) -> Repo:
    """Repo on a throwaway normalized SQLite file."""
    return Repo(tmp_path / "test.db", secret_path=tmp_path / "install.key")


@pytest.fixture
def alyssa(repo) -> HireProfile:
    profile = repo.get_hire_profile("emp-alyssa")
    assert profile is not None
    return profile
