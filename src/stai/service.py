"""One reusable chat turn: input guardrail -> agent -> output guardrails.

This is the same pipeline ``app.py`` wires up for Streamlit, packaged as a
plain function so the REST API (``stai.api``) can reuse it non-streaming.
Every turn is logged through ``stai.observability``.

LLMs are injectable (``llm`` for the agent, ``guardrail_llm`` for the input
classifier) so tests never need Ollama.
"""

from __future__ import annotations

from datetime import date

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from stai.agent import build_agent, render_system_prompt, run_agent
from stai.guardrails import REFUSALS, apply_output_guardrails, classify_input
from stai.models import Employee
from stai.observability import TurnObserver, estimate_tokens
from stai.state import Repo

HISTORY_LIMIT = 12  # same cap the Streamlit view applies


class ChatTurnResult(BaseModel):
    """Everything one chat turn produced, ready for UI or API serialization."""

    answer: str
    citations: list[str] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    escalation_id: int | None = None
    plan_changed: bool = False
    guardrail_category: str = "on_topic"
    refused: bool = False


def history_to_messages(
    history: list[dict], limit: int = HISTORY_LIMIT
) -> list[BaseMessage]:
    """Convert ``{"role", "content"}`` dicts to LangChain messages, capped."""
    out: list[BaseMessage] = []
    for m in history[-limit:]:
        if m["role"] == "user":
            out.append(HumanMessage(m["content"]))
        else:
            out.append(AIMessage(m["content"]))
    return out


def run_chat_turn(
    employee: Employee,
    repo: Repo,
    message: str,
    sim_date: date,
    history: list[dict] | None = None,
    route: str = "api",
    llm=None,
    guardrail_llm=None,
) -> ChatTurnResult:
    """Run one guarded agent turn and log it. Raises if the model call fails."""
    history = history or []
    with TurnObserver(
        route=route,
        employee_id=employee.id,
        message_chars=len(message),
    ) as obs:
        verdict = classify_input(message, llm=guardrail_llm)
        obs.record.guardrail_category = verdict.category
        if not verdict.allowed:
            answer = REFUSALS[verdict.category]
            obs.record.refused = True
            obs.record.answer_chars = len(answer)
            obs.record.est_output_tokens = estimate_tokens(answer)
            return ChatTurnResult(
                answer=answer, guardrail_category=verdict.category, refused=True
            )

        agent, capture = build_agent(employee, repo, sim_date, llm=llm)
        messages = history_to_messages(history) + [HumanMessage(message)]
        obs.record.est_input_tokens = estimate_tokens(
            render_system_prompt(employee, sim_date)
            + "".join(m["content"] for m in history[-HISTORY_LIMIT:])
            + message
        )
        raw_answer = run_agent(agent, messages)
        grounded = apply_output_guardrails(
            raw_answer, capture.used_search, capture.source_names
        )

        obs.record.answer_chars = len(grounded.answer)
        obs.record.est_output_tokens = estimate_tokens(grounded.answer)
        obs.record.tools_used = list(capture.tool_calls)
        obs.record.sources = capture.source_names
        obs.record.escalation_id = capture.escalation_id
        obs.record.plan_changed = capture.plan_changed
        return ChatTurnResult(
            answer=grounded.answer,
            citations=grounded.citations,
            sources=capture.sources,
            escalation_id=capture.escalation_id,
            plan_changed=capture.plan_changed,
            guardrail_category=verdict.category,
        )
