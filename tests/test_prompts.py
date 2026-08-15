from stai.prompts import PROMPT_VARIANTS, render_policy_prompt


def test_exact_three_frozen_prompt_variants() -> None:
    assert set(PROMPT_VARIANTS) == {"P1", "P2", "P3"}
    assert "typed" not in PROMPT_VARIANTS["P1"].lower()
    assert "claim support" in PROMPT_VARIANTS["P2"].lower()
    assert "example" in PROMPT_VARIANTS["P3"].lower()


def test_prompt_never_requests_exposed_private_reasoning() -> None:
    prompt = render_policy_prompt("P3", "Alyssa", "1.0")
    assert "do not expose" in prompt.lower()
    assert "chain-of-thought" not in prompt.lower()
    assert "Payroll, Resource Access, and HR Policies" in prompt


def test_p3_tells_react_to_stop_before_the_small_typed_finalizers() -> None:
    prompt = PROMPT_VARIANTS["P3"]
    assert "stop calling tools" in prompt
    assert "separate finalizer" in prompt
    assert "do not emit\nJSON" in prompt
