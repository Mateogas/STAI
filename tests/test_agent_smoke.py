"""Replacement ReAct smoke tests with a scripted model; no Ollama needed."""

from __future__ import annotations

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from stai.agent import build_policy_agent
from stai.guardrails import validate_policy_output
from stai.handbook import build_handbook
from stai.models import HireProfile
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
        "handbook_version": "1.0", "applicability": "applies", "evidence_state": "ready",
        "citations": [{"policy_id": "PAY-001", "handbook_version": "1.0", "page_start": policy_page}],
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
