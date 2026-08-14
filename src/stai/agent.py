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
    handbook_index=None,
    resolved_topic: str | None = None,
):
    """Build a fresh ReAct loop with schema-bounded, privacy-safe tools."""
    tools, capture = build_policy_tools(
        profile,
        repo,
        records,
        handbook_index=handbook_index,
        resolved_topic=resolved_topic,
    )
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


class LocalReactRunner:
    """Production ReAct adapter; returns ``None`` for deterministic degradation."""

    def __init__(self, repo: Repo, records, handbook_index, *, probe_timeout: float = 0.25) -> None:
        self.repo = repo
        self.records = records
        self.handbook_index = handbook_index
        self.probe_timeout = probe_timeout

    def __call__(self, resolved, profile: HireProfile, messages: list[dict]):
        from stai.guardrails import validate_policy_output, validate_response_relevance

        if not self.available():
            return None
        graph, capture = build_policy_agent(
            profile,
            self.repo,
            self.records,
            handbook_index=self.handbook_index,
            resolved_topic=resolved.topic.value if resolved.topic else None,
        )
        langchain_messages = [
            ("human" if item["role"] == "hire" else "ai", item["text"])
            for item in messages
        ]
        raw = run_agent(graph, langchain_messages)
        validated = validate_policy_output(raw, capture.retrieved_identities)
        validate_response_relevance(
            validated,
            resolved.topic.value if resolved.topic else None,
            self.records,
        )
        return validated, frozenset(capture.retrieved_identities)

    def available(self) -> bool:
        import httpx

        try:
            response = httpx.get(
                f"{settings.ollama_base_url.rstrip('/')}/api/tags",
                timeout=self.probe_timeout,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
            names = {
                str(item.get("name", "")).split(":latest")[0]
                for item in payload.get("models", [])
            }
            configured = settings.agent_model.split(":latest")[0]
            return configured in names
        except Exception:
            return False
