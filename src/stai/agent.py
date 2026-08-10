"""AISHA ReAct assembly for the bounded three-topic policy domain."""

from __future__ import annotations

try:
    from langchain.agents import create_agent as _create_agent
    _V1 = True
except ImportError:  # pragma: no cover
    from langgraph.prebuilt import create_react_agent as _create_agent
    _V1 = False

from stai.config import settings
from stai.models import HireProfile
from stai.prompts import render_policy_prompt
from stai.state import Repo
from stai.tools import build_policy_tools


def build_llm(temperature: float = 0):
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.agent_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
        seed=settings.agent_seed,
    )


def build_policy_agent(
    profile: HireProfile,
    repo: Repo,
    records,
    *,
    llm=None,
    prompt_variant: str = "P3",
):
    """Build a fresh ReAct loop with schema-bounded, privacy-safe tools."""
    tools, capture = build_policy_tools(profile, repo, records)
    version = records[0].handbook_version if records else "1.0"
    prompt = render_policy_prompt(prompt_variant, "Alyssa Reyes", version)
    model = llm or build_llm()
    if _V1:
        graph = _create_agent(model, tools, system_prompt=prompt)
    else:  # pragma: no cover
        graph = _create_agent(model, tools, prompt=prompt)
    return graph, capture


def run_agent(agent, messages) -> str:
    """Invoke the loop and return its final candidate text for validation."""
    result = agent.invoke({"messages": messages})
    content = result["messages"][-1].content
    if isinstance(content, list):
        content = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") in (None, "text")
        )
    return content or ""
