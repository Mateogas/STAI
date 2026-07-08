"""Observability logger + service pipeline logging; no Ollama needed."""

from __future__ import annotations

from datetime import date

import pytest
from langchain_core.messages import AIMessage

import stai.retriever
from stai.guardrails import REFUSALS
from stai.observability import TurnObserver, TurnRecord, estimate_tokens, log_turn, read_runs
from stai.service import run_chat_turn

from test_agent_smoke import FakeToolCallingModel, _fake_retrieve
from test_api import FakeClassifier

SIM = date(2026, 7, 7)


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hi") == 1  # short text still costs something
    assert estimate_tokens("a" * 400) == 100


def test_log_turn_roundtrip(tmp_path):
    path = tmp_path / "runs.jsonl"
    log_turn(TurnRecord(route="api", employee_id="emp-alyssa", latency_ms=42), path=path)
    log_turn(TurnRecord(route="streamlit", employee_id="emp-jomar"), path=path)
    runs = read_runs(path)
    assert len(runs) == 2
    assert runs[0]["route"] == "api" and runs[0]["latency_ms"] == 42
    assert runs[0]["ts"]  # timestamp filled in automatically
    assert read_runs(path, limit=1)[0]["employee_id"] == "emp-jomar"


def test_read_runs_missing_file(tmp_path):
    assert read_runs(tmp_path / "nope.jsonl") == []


def test_turn_observer_records_latency(tmp_path):
    path = tmp_path / "runs.jsonl"
    with TurnObserver(path=path, route="api", employee_id="emp-alyssa") as obs:
        obs.record.answer_chars = 7
    (run,) = read_runs(path)
    assert run["latency_ms"] >= 0
    assert run["answer_chars"] == 7
    assert run["error"] == ""
    assert run["agent_model"]  # model names come from settings


def test_turn_observer_records_and_reraises_errors(tmp_path):
    path = tmp_path / "runs.jsonl"
    with pytest.raises(RuntimeError):
        with TurnObserver(path=path, route="api", employee_id="emp-alyssa"):
            raise RuntimeError("ollama unreachable")
    (run,) = read_runs(path)
    assert run["error"] == "RuntimeError: ollama unreachable"


@pytest.fixture
def obs_path(tmp_path, monkeypatch):
    from stai.config import settings

    path = tmp_path / "runs.jsonl"
    monkeypatch.setattr(settings, "obs_log_path", path)
    return path


def test_run_chat_turn_logs_full_record(repo, alyssa, monkeypatch, obs_path):
    monkeypatch.setattr(stai.retriever, "retrieve", _fake_retrieve)
    fake = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search_knowledge_base", "args": {"query": "leave"}, "id": "c1"}
                ],
            ),
            AIMessage(content="File leave in the portal [source: leave_policy.md]."),
        ]
    )
    result = run_chat_turn(
        alyssa, repo, "How do I file leave?", SIM,
        llm=fake, guardrail_llm=FakeClassifier(),
    )
    assert result.citations == ["leave_policy.md"]

    (run,) = read_runs(obs_path)
    assert run["route"] == "api"
    assert run["employee_id"] == alyssa.id
    assert run["guardrail_category"] == "on_topic"
    assert run["tools_used"] == ["search_knowledge_base"]
    assert run["sources"] == ["leave_policy.md"]
    assert run["est_input_tokens"] > 0 and run["est_output_tokens"] > 0
    assert run["message_chars"] == len("How do I file leave?")
    assert run["error"] == "" and run["refused"] is False


def test_run_chat_turn_logs_refusal(repo, alyssa, obs_path):
    result = run_chat_turn(
        alyssa, repo, "write my essay", SIM, guardrail_llm=FakeClassifier("off_topic")
    )
    assert result.refused and result.answer == REFUSALS["off_topic"]

    (run,) = read_runs(obs_path)
    assert run["refused"] is True
    assert run["guardrail_category"] == "off_topic"
    assert run["tools_used"] == []


def test_run_chat_turn_logs_agent_errors(repo, alyssa, obs_path):
    class ExplodingModel(FakeToolCallingModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            raise ConnectionError("ollama down")

    with pytest.raises(ConnectionError):
        run_chat_turn(
            alyssa, repo, "hello", SIM,
            llm=ExplodingModel(responses=[]), guardrail_llm=FakeClassifier(),
        )
    (run,) = read_runs(obs_path)
    assert "ollama down" in run["error"]
