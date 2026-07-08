"""REST API tests: FastAPI TestClient + fake LLMs; no Ollama needed."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import stai.retriever
from stai.api import app, get_agent_llm, get_guardrail_llm, get_repo
from stai.config import settings
from stai.guardrails import REFUSALS

from test_agent_smoke import FakeToolCallingModel, _fake_retrieve

SIM = "2026-07-07"


class FakeClassifier:
    """Stands in for the guardrail LLM: always returns one category."""

    def __init__(self, category: str = "on_topic") -> None:
        self.category = category

    def invoke(self, _messages) -> AIMessage:
        return AIMessage(content=json.dumps({"category": self.category}))


@pytest.fixture
def client(repo, tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "obs_log_path", tmp_path / "runs.jsonl")
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_guardrail_llm] = lambda: FakeClassifier()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _use_agent(fake: FakeToolCallingModel) -> None:
    app.dependency_overrides[get_agent_llm] = lambda: fake


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["employees"] == 3
    assert body["agent_model"] == settings.agent_model
    assert "fictionalized" in body["disclaimer"]


def test_chat_unknown_employee_is_404(client):
    resp = client.post(
        "/chat", json={"employee_id": "emp-nobody", "message": "hi", "sim_date": SIM}
    )
    assert resp.status_code == 404


def test_chat_off_topic_refusal(client):
    app.dependency_overrides[get_guardrail_llm] = lambda: FakeClassifier("off_topic")
    resp = client.post(
        "/chat",
        json={"employee_id": "emp-alyssa", "message": "capital of France?", "sim_date": SIM},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == REFUSALS["off_topic"]
    assert body["guardrail_category"] == "off_topic"
    assert body["refused"] is True
    assert body["sources"] == [] and body["citations"] == []


def test_chat_kb_answer_with_citation(client, monkeypatch):
    monkeypatch.setattr(stai.retriever, "retrieve", _fake_retrieve)
    _use_agent(
        FakeToolCallingModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_knowledge_base",
                            "args": {"query": "leave requests"},
                            "id": "call_1",
                        }
                    ],
                ),
                AIMessage(content="File leave in the demo HR portal [source: leave_policy.md]."),
            ]
        )
    )
    resp = client.post(
        "/chat",
        json={"employee_id": "emp-alyssa", "message": "How do I file leave?", "sim_date": SIM},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "[source: leave_policy.md]" in body["answer"]
    assert body["citations"] == ["leave_policy.md"]
    assert body["sources"][0]["source"] == "leave_policy.md"
    assert body["guardrail_category"] == "on_topic"
    assert body["refused"] is False


def test_chat_escalation_returns_ticket_id(client, repo):
    _use_agent(
        FakeToolCallingModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "escalate_to_hr",
                            "args": {"question": "Reset my training sandbox?"},
                            "id": "call_1",
                        }
                    ],
                ),
                AIMessage(content="I've filed a ticket with People Experience."),
            ]
        )
    )
    resp = client.post(
        "/chat",
        json={"employee_id": "emp-alyssa", "message": "sandbox is broken", "sim_date": SIM},
    )
    body = resp.json()
    assert body["escalation_id"] is not None
    assert repo.list_escalations(status="open")[0].id == body["escalation_id"]


def test_chat_complete_task_reports_plan_changed(client, repo):
    _use_agent(
        FakeToolCallingModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "complete_task",
                            "args": {"task": "laptop"},
                            "id": "call_1",
                        }
                    ],
                ),
                AIMessage(content="Done - laptop pickup is checked off."),
            ]
        )
    )
    resp = client.post(
        "/chat",
        json={"employee_id": "emp-alyssa", "message": "mark laptop pickup done", "sim_date": SIM},
    )
    assert resp.json()["plan_changed"] is True
    done, _total = repo.progress("emp-alyssa")
    assert done == 1


def test_chat_persists_turns_and_reuses_history(client, repo):
    _use_agent(FakeToolCallingModel(responses=[AIMessage(content="Happy to help, Alyssa!")]))
    client.post(
        "/chat",
        json={"employee_id": "emp-alyssa", "message": "hello there", "sim_date": SIM},
    )
    stored = repo.list_chat_messages("emp-alyssa")
    assert [m.role for m in stored] == ["user", "assistant"]
    assert stored[0].content == "hello there"
    assert stored[1].content == "Happy to help, Alyssa!"

    # Second call without history: the persisted turns become the context.
    _use_agent(FakeToolCallingModel(responses=[AIMessage(content="Still here!")]))
    client.post(
        "/chat",
        json={"employee_id": "emp-alyssa", "message": "are you there?", "sim_date": SIM},
    )
    assert len(repo.list_chat_messages("emp-alyssa")) == 4
