"""Replacement ReAct smoke tests with a scripted model; no Ollama needed."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.errors import GraphRecursionError

from stai.agent import (
    AgentUnavailableError,
    LocalReactRunner,
    _grounded_from_react,
    _invoke_typed,
    build_finalizer_llm,
    build_policy_agent,
    run_agent,
)
from stai.config import settings
from stai.guardrails import validate_policy_output
from stai.handbook import build_handbook
from stai.models import AgentPlanDraft, HireProfile
from stai.retriever import load_page_records


class FakeToolCallingModel(BaseChatModel):
    responses: list[AIMessage]
    index: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        message = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools, **kwargs):
        return self

    @property
    def _llm_type(self):
        return "fake-tool-calling"


def test_react_search_then_validated_typed_response(repo, tmp_path):
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    policy_page = next(row.page for row in records if row.policy_id == "PAY-001" and row.page_kind == "policy")
    final = {
        "type": "grounded_answer", "text": "Payroll policy is grounded.",
        "handbook_version": "1.1", "applicability": "applies", "evidence_state": "ready",
        "citations": [{"policy_id": "PAY-001", "handbook_version": "1.1", "page_start": policy_page}],
        "claims": [{"text": "Payroll policy is grounded.", "citation_indexes": [0]}],
    }
    fake = FakeToolCallingModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "search_handbook", "args": {"query": "PAY-001"}, "id": "c1"}]),
        AIMessage(content=json.dumps(final)),
    ])
    agent, capture = build_policy_agent(HireProfile.alyssa(), repo, records, llm=fake)
    result = agent.invoke({"messages": [("user", "What does PAY-001 say?")]})
    assert any(isinstance(message, ToolMessage) for message in result["messages"])
    assert capture.tool_calls == ["search_handbook"]
    validated = validate_policy_output(result["messages"][-1].content, capture.retrieved_identities)
    assert validated.type == "grounded_answer"


def test_react_escalation_tool_offers_route_without_case_mutation(repo, tmp_path):
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    fake = FakeToolCallingModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "offer_escalation", "args": {"policy_id": "PAY-001", "topic": "payroll"}, "id": "c1"}]),
        AIMessage(content='{"type":"abstention"}'),
    ])
    agent, capture = build_policy_agent(HireProfile.alyssa(), repo, records, llm=fake)
    agent.invoke({"messages": [("user", "Who can clarify PAY-001?")]})
    assert capture.tool_calls == ["offer_escalation"]
    assert repo.list_escalation_cases() == []


def test_react_model_call_limit_stops_a_repeating_tool_loop(repo, tmp_path):
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)

    class RepeatingToolModel(FakeToolCallingModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            self.index += 1
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_handbook",
                        "args": {"query": "office clothing"},
                        "id": f"loop-{self.index}",
                    }
                ],
            )
            return ChatResult(generations=[ChatGeneration(message=message)])

    fake = RepeatingToolModel(responses=[])
    agent, capture = build_policy_agent(HireProfile.alyssa(), repo, records, llm=fake)

    result = agent.invoke(
        {"messages": [("user", "What clothing can I wear in the office?")]},
        config={"recursion_limit": settings.agent_recursion_limit},
    )

    assert result["messages"][-1].content.startswith("Model call limits exceeded:")
    assert len(capture.tool_calls) == settings.agent_model_call_limit


def test_run_agent_maps_graph_recursion_to_safe_domain_error(monkeypatch):
    class RecursingGraph:
        recursion_limit = None

        def invoke(self, *_args, **kwargs):
            self.recursion_limit = kwargs["config"]["recursion_limit"]
            raise GraphRecursionError("loop")

    monkeypatch.setattr(settings, "agent_recursion_limit", 16)
    graph = RecursingGraph()
    with pytest.raises(AgentUnavailableError, match="bounded execution budget"):
        run_agent(graph, [("user", "office clothing")], model=object())
    assert graph.recursion_limit >= settings.agent_model_call_limit * 4 + 8


def test_typed_finalizer_uses_native_json_schema_and_repairs_missing_fields():
    class StubStructuredModel:
        def __init__(self):
            self.method = None
            self.calls = 0

        def with_structured_output(self, _schema, *, method, include_raw):
            self.method = method
            assert include_raw is True
            return self

        def invoke(self, _messages):
            self.calls += 1
            if self.calls == 1:
                content = '{"dialogue_act":"question","topic":"payroll","policy_ids":["PAY-001"]}'
                error = ValueError("standalone_query missing")
            else:
                content = json.dumps(
                    {
                        "dialogue_act": "question",
                        "topic": "payroll",
                        "policy_ids": ["PAY-001"],
                        "standalone_query": "How to view payroll",
                        "agent_actions": ["retrieve_policy"],
                    }
                )
                error = None
            return {
                "parsed": None,
                "raw": AIMessage(content=f"```json\n{content}\n```"),
                "parsing_error": error,
            }

    model = StubStructuredModel()
    plan = _invoke_typed(
        model,
        AgentPlanDraft,
        "Return the payroll plan.",
        {"conversation_messages": ["How to view payroll"]},
    )

    assert model.method == "json_schema"
    assert model.calls == 2
    assert plan.standalone_query == "How to view payroll"
    assert plan.policy_ids == ["PAY-001"]


def test_typed_finalizer_failure_reports_a_safe_stage():
    class InvalidStructuredModel:
        def with_structured_output(self, _schema, *, method, include_raw):
            assert method == "json_schema" and include_raw is True
            return self

        def invoke(self, _messages):
            return {
                "parsed": None,
                "raw": AIMessage(content="{}"),
                "parsing_error": None,
            }

    with pytest.raises(AgentUnavailableError) as failure:
        _invoke_typed(
            InvalidStructuredModel(),
            AgentPlanDraft,
            "Return the payroll plan.",
            {"conversation_messages": ["How to view payroll"]},
        )
    assert failure.value.stage == "structured_output:AgentPlanDraft"


def test_finalizer_model_and_timeouts_are_independently_configurable(monkeypatch):
    monkeypatch.setattr(settings, "agent_model", "gemma4:12b")
    monkeypatch.setattr(settings, "finalizer_model", "gemma4:e4b")
    monkeypatch.setattr(settings, "agent_request_timeout_seconds", 47.0)
    monkeypatch.setattr(settings, "agent_probe_timeout_seconds", 2.5)

    finalizer = build_finalizer_llm()
    runner = LocalReactRunner(object(), [], object())

    assert finalizer.model == "gemma4:e4b"
    assert finalizer.client_kwargs == {"timeout": 47.0}
    assert runner.probe_timeout == 2.5


def test_grounded_response_reuses_react_synthesis_and_captured_evidence():
    evidence = [
        {
            "policy_id": "PAY-002",
            "handbook_version": "1.1",
            "page": 12,
            "content": "Payslips are available in the fictional portal.",
        }
    ]
    capture = SimpleNamespace(
        evidence_metadata=[
            {
                "policy_id": "PAY-002",
                "handbook_version": "1.1",
                "page": 12,
                "applicability": "applies",
            }
        ]
    )

    response = _grounded_from_react(
        "Open the fictional Employee Self-Service Portal.", evidence, capture
    )

    assert response.text == "Open the fictional Employee Self-Service Portal."
    assert response.citations[0].policy_id == "PAY-002"
    assert response.claims[0].text == evidence[0]["content"]
    assert response.claims[0].citation_indexes == [0]
