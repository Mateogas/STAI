"""AISHA ReAct assembly for the bounded three-topic policy domain."""

from __future__ import annotations

import json
from dataclasses import dataclass

try:
    from langchain.agents import create_agent as _create_agent
    _V1 = True
except ImportError:  # pragma: no cover
    from langgraph.prebuilt import create_react_agent as _create_agent
    _V1 = False

from stai.config import settings
from stai.handbook import ACTIVE_HANDBOOK_VERSION
from stai.models import (
    AgentAbstentionDraft,
    AgentCaseActionDraft,
    AgentClaimsDraft,
    AgentClarificationDraft,
    AgentEscalationDraft,
    AgentGroundedDraft,
    AgentPlanDraft,
    AgentResponseTypeDraft,
    AgentTurnDecision,
    ApplicabilityStatus,
    EvidenceState,
    HireProfile,
)
from stai.prompts import render_policy_prompt
from stai.state import Repo
from stai.tools import build_policy_tools


class AgentUnavailableError(RuntimeError):
    """The required conversational model is not available for a supported turn."""


@dataclass(frozen=True)
class AgentRun:
    decision: AgentTurnDecision
    capture: object


def build_llm(temperature: float = 0):
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.agent_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
        seed=settings.agent_seed,
        num_ctx=settings.agent_context_window,
    )


def build_policy_agent(
    profile: HireProfile,
    repo: Repo,
    records,
    *,
    llm=None,
    prompt_variant: str = "P3",
    handbook_index=None,
):
    """Build a fresh ReAct loop with schema-bounded, privacy-safe tools."""
    tools, capture = build_policy_tools(
        profile,
        repo,
        records,
        handbook_index=handbook_index,
    )
    version = records[0].handbook_version if records else ACTIVE_HANDBOOK_VERSION
    prompt = render_policy_prompt(prompt_variant, "Alyssa Reyes", version)
    model = llm or build_llm()
    if _V1:
        graph = _create_agent(model, tools, system_prompt=prompt)
    else:  # pragma: no cover
        graph = _create_agent(model, tools, prompt=prompt)
    return graph, capture


def run_agent(agent, messages, *, model=None, capture=None) -> AgentTurnDecision:
    """Run ReAct, then force its plan and response through small typed schemas."""
    result = agent.invoke(
        {"messages": messages},
        config={"recursion_limit": settings.agent_recursion_limit},
    )
    final_model = model or build_llm()
    evidence = []
    if capture is not None:
        for identity, content in getattr(capture, "evidence_contents", {}).items():
            evidence.append(
                {
                    "policy_id": identity[0],
                    "handbook_version": identity[1],
                    "page": identity[2],
                    "content": content,
                }
            )
    user_messages = [
        item.content
        for item in result["messages"]
        if type(item).__name__ == "HumanMessage"
    ]
    synthesis = result["messages"][-1].content
    finalizer_input = {
        "conversation_messages": user_messages,
        "react_synthesis": synthesis,
        "retrieved_evidence": evidence,
    }
    plan_input = {
        "conversation_messages": user_messages,
        "react_synthesis": synthesis,
        "retrieved_evidence_identities": [
            {key: item[key] for key in ("policy_id", "handbook_version", "page")}
            for item in evidence
        ],
    }
    plan = _invoke_typed(
        final_model,
        AgentPlanDraft,
        (
            "Return the typed intent plan for the completed AISHA ReAct turn. Infer intent "
            "from the full conversation, not keywords. dialogue_act is the user's intent: "
            "question, follow_up, clarification, help_request, escalation_request, consent, "
            "action_status, capability_discovery, greeting, or unsupported. Use lowercase "
            "enum values and only listed evidence identities. Every policy question or "
            "follow-up must select exactly one topic. policy_ids contains only policies that "
            "directly answer the user's goal, not every retrieved candidate. Contrastive "
            "wording matters: a regular payroll-schedule question is not a first-pay cutoff "
            "question even if both concepts occur in retrieved pages."
        ),
        plan_input,
    )
    if not _plan_is_coherent(plan):
        plan = _invoke_typed(
            final_model,
            AgentPlanDraft,
            (
                "Repair the AISHA plan semantically. A question or follow_up must have exactly "
                "one topic. Remove retrieved distractors from policy_ids; every retained policy "
                "ID must belong to that topic and directly answer the user's goal. Preserve "
                "contrastive intent and use lowercase enum values."
            ),
            {**plan_input, "invalid_plan": plan.model_dump(mode="json")},
        )
        if not _plan_is_coherent(plan):
            raise AgentUnavailableError("agent plan did not resolve one coherent policy topic")
    response_type = _invoke_typed(
        final_model,
        AgentResponseTypeDraft,
        (
            "Choose exactly one response shape for the completed AISHA turn: grounded_answer "
            "when evidence answers it; clarification_request when one prerequisite or intent "
            "is ambiguous; abstention when unsupported or evidence is absent; escalation_offer "
            "only for cited partial evidence with a material gap; case_action only for consent "
            "or status of an existing offer/case."
        ),
        {**plan_input, "typed_plan": plan.model_dump(mode="json")},
    ).response_type
    if not _plan_matches_response(plan, response_type):
        plan = _invoke_typed(
            final_model,
            AgentPlanDraft,
            (
                f"Repair the user-intent plan so it is coherent with response_type "
                f"{response_type}. dialogue_act describes what the user did, not the answer. "
                "A direct policy question is question; a contextual question is follow_up; "
                "clarification means the user supplied a requested missing detail. case_action "
                "requires consent or action_status. Preserve the resolved topic and direct "
                "policy IDs."
            ),
            {
                **plan_input,
                "invalid_plan": plan.model_dump(mode="json"),
                "response_type": response_type,
            },
        )
        if not _plan_is_coherent(plan) or not _plan_matches_response(plan, response_type):
            raise AgentUnavailableError("agent plan and response type remained inconsistent")
    response_schemas = {
        "grounded_answer": AgentGroundedDraft,
        "clarification_request": AgentClarificationDraft,
        "abstention": AgentAbstentionDraft,
        "escalation_offer": AgentEscalationDraft,
        "case_action": AgentCaseActionDraft,
    }
    scoped_evidence = [
        item for item in evidence if not plan.policy_ids or item["policy_id"] in plan.policy_ids
    ]
    response_input = {
        **finalizer_input,
        "retrieved_evidence": scoped_evidence,
        "typed_plan": plan.model_dump(mode="json"),
        "response_type": response_type,
    }
    response_instructions = (
        f"Return only the typed {response_type} draft for AISHA Handbook v1.1. "
        "Use only retrieved_evidence. For a grounded answer, every claim.text must equal "
        "one complete evidence content value copied character-for-character; do not shorten "
        "or paraphrase it. citation_indexes must point to that content's citation. For "
        "escalation, safe_known_text must be an exact contiguous excerpt and only a missing "
        "procedure, unclear route, unclear exception, or policy conflict is eligible. Do not "
        "invent case or offer IDs."
    )
    try:
        response = _invoke_typed(
            final_model,
            response_schemas[response_type],
            response_instructions,
            response_input,
        )
    except AgentUnavailableError as exc:
        raise AgentUnavailableError(
            f"response formatting failed for plan topic={plan.topic} "
            f"policy_ids={plan.policy_ids} evidence_pages={len(scoped_evidence)}: {exc}"
        ) from exc
    if response_type == "grounded_answer" and not _claims_are_exact(
        response, scoped_evidence
    ):
        repaired_claims = _invoke_typed(
            final_model,
            AgentClaimsDraft,
            (
                "Return only supporting claims for the answer. Every claim.text must be a "
                "character-for-character contiguous quote copied from exactly one "
                "retrieved_evidence.content. Do not paraphrase, summarize, or copy the user "
                "question. citation_indexes must point to that evidence page's position in "
                "the answer citations."
            ),
            {
                "answer_text": response.text,
                "citations": [item.model_dump(mode="json") for item in response.citations],
                "retrieved_evidence": scoped_evidence,
                "invalid_draft": response.model_dump(mode="json"),
            },
        )
        response = response.model_copy(update={"claims": repaired_claims.claims})
        if not _claims_are_exact(response, scoped_evidence):
            raise AgentUnavailableError("grounded claims did not copy retrieved evidence exactly")
    payload = plan.model_dump(mode="json")
    payload["response_type"] = response_type
    response_payload = response.model_dump(mode="json")
    if response_type == "escalation_offer":
        response_payload.update(
            applicability=ApplicabilityStatus.APPLIES.value,
            evidence_state=EvidenceState.INSUFFICIENT.value,
        )
    elif response_type == "case_action":
        response_payload.update(
            applicability=ApplicabilityStatus.APPLIES.value,
            evidence_state=EvidenceState.READY.value,
        )
    payload.update(response_payload)
    return AgentTurnDecision.model_validate(payload)


def _claims_are_exact(response, evidence: list[dict]) -> bool:
    contents = [" ".join(item["content"].casefold().split()) for item in evidence]
    return bool(response.claims) and all(
        any(
            " ".join(claim.text.casefold().split()) in content
            for content in contents
        )
        and bool(claim.citation_indexes)
        for claim in response.claims
    )


def _plan_is_coherent(plan: AgentPlanDraft) -> bool:
    if plan.dialogue_act.value in {"question", "follow_up"} and plan.topic is None:
        return False
    prefixes = {
        "PAY": "payroll",
        "ACC": "resource_access",
        "HRP": "hr_policies",
    }
    return all(
        plan.topic is None or prefixes.get(policy_id.split("-", 1)[0]) == plan.topic.value
        for policy_id in plan.policy_ids
    )


def _plan_matches_response(plan: AgentPlanDraft, response_type: str) -> bool:
    if response_type == "grounded_answer":
        return plan.dialogue_act.value in {
            "question",
            "follow_up",
            "clarification",
            "capability_discovery",
        }
    if response_type == "case_action":
        return plan.dialogue_act.value in {"consent", "action_status"}
    return True


def _invoke_typed(model, schema, instructions: str, payload: dict):
    """Invoke one small function schema and retry only malformed structured output."""
    finalizer = model.with_structured_output(
        schema,
        method="function_calling",
        include_raw=True,
    )
    messages = [
        ("system", instructions),
        ("human", json.dumps(payload, default=str)),
    ]
    finalized = finalizer.invoke(messages)
    if finalized.get("parsed") is not None:
        return finalized["parsed"]
    calls = getattr(finalized.get("raw"), "tool_calls", [])
    attempted = calls[0]["args"] if calls else {}
    repaired = finalizer.invoke(
        [
            *messages,
            (
                "human",
                "Repair the malformed structured result. Return every required field. "
                f"Validation error: {finalized.get('parsing_error')}. "
                f"Invalid attempt: {json.dumps(attempted, default=str)}",
            ),
        ]
    )
    if repaired.get("parsed") is None:
        raise AgentUnavailableError(
            f"agent returned invalid {schema.__name__}: {repaired.get('parsing_error')}"
        )
    return repaired["parsed"]


class LocalReactRunner:
    """Required production ReAct adapter; it never substitutes a local answer path."""

    def __init__(self, repo: Repo, records, handbook_index, *, probe_timeout: float = 0.25) -> None:
        self.repo = repo
        self.records = records
        self.handbook_index = handbook_index
        self.probe_timeout = probe_timeout

    def __call__(
        self,
        profile: HireProfile,
        messages: list[dict],
        runtime_context: dict,
    ) -> AgentRun:
        if not self.available():
            raise AgentUnavailableError(
                f"required Ollama model {settings.agent_model!r} is unavailable"
            )
        model = build_llm()
        graph, capture = build_policy_agent(
            profile,
            self.repo,
            self.records,
            llm=model,
            handbook_index=self.handbook_index,
        )
        langchain_messages = [("system", "Private runtime context (authoritative): " + json.dumps(runtime_context))]
        langchain_messages.extend(
            ("human" if item["role"] == "hire" else "ai", item["text"])
            for item in messages
        )
        return AgentRun(
            run_agent(graph, langchain_messages, model=model, capture=capture),
            capture,
        )

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
