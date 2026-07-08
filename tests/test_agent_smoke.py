"""Agent smoke tests with a scripted fake LLM; no Ollama needed."""

from __future__ import annotations

from datetime import date

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import stai.retriever
from stai.agent import build_agent, run_agent
from stai.guardrails import apply_output_guardrails

SIM = date(2026, 7, 7)


class FakeToolCallingModel(BaseChatModel):
    """Plays back a fixed list of AIMessages, one per model call."""

    responses: list[AIMessage]
    idx: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        msg = self.responses[min(self.idx, len(self.responses) - 1)]
        self.idx += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):
        return self

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling"


def _fake_retrieve(query, k=None, doc_type=None, department=None):
    return [
        Document(
            page_content="Leave requests are filed in the demo HR portal.",
            metadata={
                "source": "leave_policy.md",
                "title": "Leave and Absence Guide",
                "doc_type": "policy",
                "department": "all",
            },
        )
    ]


def test_happy_path_kb_answer_with_citation(repo, alyssa, monkeypatch):
    monkeypatch.setattr(stai.retriever, "retrieve", _fake_retrieve)
    fake = FakeToolCallingModel(
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
    agent, capture = build_agent(alyssa, repo, SIM, llm=fake)
    result = agent.invoke({"messages": [("user", "How do I file leave?")]})

    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert tool_msgs and "leave_policy.md" in tool_msgs[0].content
    assert capture.used_search
    assert capture.source_names == ["leave_policy.md"]

    final = result["messages"][-1].content
    grounded = apply_output_guardrails(final, capture.used_search, capture.source_names)
    assert "[source: leave_policy.md]" in grounded.answer
    assert grounded.citations == ["leave_policy.md"]


def test_escalation_path_files_real_ticket(repo, alyssa):
    fake = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "escalate_to_hr",
                        "args": {
                            "question": "Can someone reset my training sandbox?",
                            "details": "not found in handbook",
                        },
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(content="I've filed escalation #1 with People Experience."),
        ]
    )
    agent, capture = build_agent(alyssa, repo, SIM, llm=fake)
    answer = run_agent(agent, [("user", "Can someone reset my training sandbox?")])

    assert "escalation" in answer.lower()
    assert capture.escalation_id is not None
    open_escalations = repo.list_escalations(status="open")
    assert len(open_escalations) == 1
    assert open_escalations[0].employee_id == alyssa.id


def test_direct_answer_no_tools(repo, alyssa):
    fake = FakeToolCallingModel(
        responses=[AIMessage(content="Hola Alyssa. Encantada de ayudarte con tu onboarding.")]
    )
    agent, capture = build_agent(alyssa, repo, SIM, llm=fake)
    answer = run_agent(agent, [("user", "hola!")])

    assert "Hola" in answer
    assert not capture.used_search
    grounded = apply_output_guardrails(answer, capture.used_search, capture.source_names)
    assert grounded.answer == answer
