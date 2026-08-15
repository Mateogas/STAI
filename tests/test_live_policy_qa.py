"""Live end-to-end policy Q&A tests against a real Ollama endpoint.

These tests are deselected by default (``-m 'not live'`` in pyproject). Opt in
with ``STAI_RUN_LIVE=1`` and an Ollama endpoint that serves the configured
``agent_model`` and ``guardrail_model``. Everything is env-driven, so the same
tests run against the local GPU or a remote endpoint::

    $env:STAI_RUN_LIVE = "1"
    $env:STAI_OLLAMA_BASE_URL = "http://103.231.240.155:11434"
    $env:STAI_AGENT_MODEL = "qwen2.5:latest"
    $env:STAI_GUARDRAIL_MODEL = "qwen2.5:latest"
    uv run pytest tests/test_live_policy_qa.py -m live

They prove the properties the mocked suite cannot: that a basic question is
actually answered, quickly, by the real agent path (not a degraded fallback),
that the resolved policy reaches retrieval, and that the live model's structured
output conforms to the typed schemas.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

# The basic, broad question that previously failed live: it must resolve to the
# first-pay schedule policy, which real lexical retrieval already ranks first.
BASIC_QUESTION = "When will I receive my first pay?"
EXPECTED_POLICY_ID = "PAY-001"
ALLOWED_POLICY_IDS = {"PAY-001"}
RETRIEVAL_TOOLS = {"search_handbook", "read_policy_bundle", "discover_policies"}


def _served_model_tags(base_url: str, timeout: float = 8.0) -> set[str]:
    import httpx

    response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
    response.raise_for_status()
    return {str(item.get("name", "")) for item in response.json().get("models", [])}


def _model_present(model: str, served: set[str]) -> bool:
    if model in served:
        return True
    # Allow the bare-name convenience: "qwen2.5" matches a served "qwen2.5:latest".
    return ":" not in model and f"{model}:latest" in served


def live_skip_reason() -> str | None:
    """Return why the live suite cannot run here, or ``None`` when it can."""
    from stai.config import settings

    if not os.getenv("STAI_RUN_LIVE"):
        return "set STAI_RUN_LIVE=1 to run the live Ollama suite"
    try:
        served = _served_model_tags(settings.ollama_base_url)
    except Exception as exc:  # noqa: BLE001 - report any connectivity failure
        return f"Ollama endpoint {settings.ollama_base_url} unreachable: {exc}"
    missing = [
        model
        for model in (settings.agent_model, settings.guardrail_model)
        if not _model_present(model, served)
    ]
    if missing:
        return (
            f"required models missing on {settings.ollama_base_url}: "
            f"{sorted(missing)} (served: {sorted(served)})"
        )
    return None


_SKIP = live_skip_reason()
if _SKIP:
    pytest.skip(_SKIP, allow_module_level=True)


@pytest.fixture(scope="module")
def live_records():
    from stai.retriever import load_page_records

    root = Path(__file__).resolve().parents[1]
    return load_page_records(root / "handbook" / "dist" / "rag-pages.jsonl")


@pytest.fixture(scope="module")
def live_repo(tmp_path_factory):
    from stai.state import Repo

    directory = tmp_path_factory.mktemp("live")
    return Repo(directory / "live.db", secret_path=directory / "install.key")


@pytest.fixture(scope="module")
def live_runtime(live_repo, live_records):
    """A real service plus the real ReAct runner, warmed to steady state."""
    from stai.agent import LocalReactRunner
    from stai.guardrails import LocalInputClassifier
    from stai.retriever import InMemoryHandbookIndex
    from stai.service import AishaService

    index = InMemoryHandbookIndex(live_records)
    runner = LocalReactRunner(live_repo, live_records, index)
    if not runner.available():
        pytest.skip("configured agent model is not available at the endpoint")
    classifier = LocalInputClassifier()
    service = AishaService(
        live_repo,
        live_records,
        handbook_index=index,
        agent_runner=runner,
        input_classifier=classifier,
    )
    profile = live_repo.get_hire_profile("emp-alyssa")
    # Warm the agent + finalizer weights so the latency test measures the
    # steady-state turn, not a one-time cold model load. Best-effort: a warmup
    # hiccup must not mask the per-test results below.
    warmup = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    try:
        service.send_message(warmup["id"], BASIC_QUESTION)
    except Exception:  # noqa: BLE001 - warmup is a latency aid, not an assertion
        pass
    return {
        "service": service,
        "runner": runner,
        "index": index,
        "records": live_records,
        "repo": live_repo,
        "profile": profile,
    }


def _fresh_answer(live_runtime, question: str = BASIC_QUESTION):
    service = live_runtime["service"]
    conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    started = time.perf_counter()
    response = service.send_message(conversation["id"], question)
    elapsed = time.perf_counter() - started
    return conversation, response, elapsed


def _direct_run(live_runtime, question: str = BASIC_QUESTION):
    """Call the real runner directly to inspect its capture and typed decision."""
    runner = live_runtime["runner"]
    profile = live_runtime["profile"]
    runtime_context = {
        "conversation_id": "live-probe",
        "simulated_date": "2026-08-10",
        "confirmed_hire_profile": profile.model_dump(mode="json"),
        "latest_turn": None,
        "pending_escalation_offer": None,
    }
    return runner(profile, [{"role": "hire", "text": question}], runtime_context)


# 1. Live end-to-end "basic question" smoke test.
def test_basic_first_pay_question_is_answered_and_grounded(live_runtime):
    from stai.models import GroundedPolicyAnswer

    _conversation, response, _elapsed = _fresh_answer(live_runtime)

    assert isinstance(response, GroundedPolicyAnswer), (
        f"expected a grounded answer, got {type(response).__name__}: "
        f"{getattr(response, 'text', '')!r}"
    )
    cited = {citation.policy_id for citation in response.citations}
    assert EXPECTED_POLICY_ID in cited, f"first-pay answer must cite PAY-001, cited {sorted(cited)}"
    assert cited <= ALLOWED_POLICY_IDS, f"answer cited out-of-scope policies: {sorted(cited)}"
    assert response.claims, "a grounded answer must carry at least one supported claim"
    assert len(response.text.strip()) >= 20, "the answer text is implausibly short"


# 2. Maximum response-time check.
def test_basic_question_completes_within_the_latency_budget(live_runtime):
    from stai.config import settings

    _conversation, _response, elapsed = _fresh_answer(live_runtime)

    budget = settings.live_turn_budget_seconds
    assert elapsed <= budget, (
        f"live turn took {elapsed:.1f}s, exceeding the "
        f"{budget:.1f}s budget (STAI_LIVE_TURN_BUDGET_SECONDS)"
    )


# 3. Execution mode is genuinely agent, not degraded/deterministic.
def test_basic_question_runs_the_agent_path_not_a_fallback(live_runtime):
    conversation, _response, _elapsed = _fresh_answer(live_runtime)

    context = live_runtime["repo"].get_latest_turn_context(conversation["id"])
    assert context is not None, "the turn did not persist a result row"
    assert context["execution_mode"] == "agent", (
        "the turn did not run the live agent path; persisted execution_mode="
        f"{context['execution_mode']!r}"
    )


# 4. Planner-resolved policy IDs reach the agent's retrieval tool.
def test_resolved_policy_id_reaches_retrieval_and_drives_the_answer(live_runtime):
    from stai.models import GroundedPolicyAnswer

    run = _direct_run(live_runtime)
    capture = run.capture
    decision = run.decision

    called = list(getattr(capture, "tool_calls", []))
    assert set(called) & RETRIEVAL_TOOLS, f"no retrieval tool was invoked; tools called: {called}"

    retrieved_ids = {identity[0] for identity in getattr(capture, "retrieved_identities", set())}
    assert EXPECTED_POLICY_ID in retrieved_ids, (
        "the correct policy never reached retrieval; "
        f"retrieved {sorted(retrieved_ids)}"
    )

    # The resolved plan's policy IDs must correspond to retrieved evidence and
    # stay within the in-scope answer set (not the wrong PAY-003/PAY-006).
    resolved = set(decision.policy_ids)
    assert EXPECTED_POLICY_ID in resolved, f"plan did not resolve PAY-001; resolved {sorted(resolved)}"
    assert resolved <= ALLOWED_POLICY_IDS, f"plan resolved out-of-scope policies: {sorted(resolved)}"
    assert resolved <= retrieved_ids, "plan resolved a policy that retrieval never returned"

    response = decision.response
    if response.response_type == "grounded_answer":
        cited = {citation.policy_id for citation in response.citations}
        assert EXPECTED_POLICY_ID in cited


# 5. Live schema-conformance of the model's structured output.
def test_live_model_structured_output_conforms_to_typed_schemas(live_runtime):
    from stai.guardrails import validate_policy_output
    from stai.models import AgentResponseDraft, AgentTurnDecision

    run = _direct_run(live_runtime)

    # The typed decision returned by the live finalizer must round-trip through
    # the wire schema without repair, proving valid structured output.
    decision = AgentTurnDecision.model_validate(run.decision.model_dump(mode="json"))
    draft = decision.response
    assert isinstance(draft, AgentResponseDraft)
    assert draft.response_type in {
        "grounded_answer",
        "clarification_request",
        "abstention",
        "escalation_offer",
        "case_action",
    }

    # And the public typed response the wire schema projects must validate as a
    # known discriminated PolicyResponse.
    if draft.response_type == "grounded_answer":
        payload = {
            "type": "grounded_answer",
            "text": draft.text,
            "handbook_version": draft.handbook_version,
            "applicability": draft.applicability.value,
            "evidence_state": draft.evidence_state.value,
            "citations": [citation.model_dump(mode="json") for citation in draft.citations],
            "claims": [claim.model_dump(mode="json") for claim in draft.claims],
        }
        identities = set(getattr(run.capture, "retrieved_identities", set()))
        validated = validate_policy_output(json.dumps(payload), identities)
        assert validated.type == "grounded_answer", (
            "a grounded draft must validate as a grounded answer against its own "
            f"retrieved evidence, got {validated.type}"
        )
    else:
        # Non-grounded outcomes still carry a schema-consistent shape.
        assert draft.text.strip(), "every typed draft must carry non-empty text"
        if draft.response_type == "clarification_request":
            assert draft.question, "clarification drafts must include a question"
        if draft.response_type == "abstention":
            assert draft.reason, "abstention drafts must include a reason"
