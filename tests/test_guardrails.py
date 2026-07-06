from __future__ import annotations

from stai.guardrails import (
    NOT_IN_HANDBOOK,
    classify_input,
    enforce_citations,
    extract_citations,
    parse_verdict,
    redact_pii,
)


from types import SimpleNamespace


class FakeLLM:
    def __init__(self, reply: str):
        self.reply = reply

    def invoke(self, prompt: str):
        return SimpleNamespace(content=self.reply)


# ------------------------------------------------------------- verdict parse

def test_parse_verdict_clean_json():
    v = parse_verdict('{"category": "off_topic", "reason": "trivia"}')
    assert v.category == "off_topic" and not v.allowed


def test_parse_verdict_json_wrapped_in_prose():
    v = parse_verdict('Sure! Here you go: {"category": "injection"} hope that helps')
    assert v.category == "injection"


def test_parse_verdict_keyword_fallback():
    v = parse_verdict("this looks like off_topic to me")
    assert v.category == "off_topic"


def test_parse_verdict_garbage_fails_open():
    v = parse_verdict("¯\\_(ツ)_/¯")
    assert v.category == "on_topic" and v.allowed


def test_parse_verdict_fewshot_echo_fails_open():
    # A tiny model in JSON mode may echo the whole few-shot transcript back;
    # every category name appears -> ambiguous -> must NOT guess "injection".
    echo = (
        '{"messages": [{"text": "{\\"category\\": \\"on_topic\\"}"},'
        ' {"text": "{\\"category\\": \\"off_topic\\"}"},'
        ' {"text": "{\\"category\\": \\"injection\\"}"}]}'
    )
    v = parse_verdict(echo)
    assert v.category == "on_topic" and "fail-open" in v.reason


def test_classify_input_uses_injected_llm():
    v = classify_input("what is the capital of France?", llm=FakeLLM('{"category": "off_topic"}'))
    assert not v.allowed


def test_classify_input_fails_open_when_llm_raises():
    class Boom:
        def invoke(self, _):
            raise ConnectionError("ollama down")

    v = classify_input("how many vacation days do I get?", llm=Boom())
    assert v.allowed


# ---------------------------------------------------------------- citations

def test_extract_citations_dedupes():
    text = "20 days [source: leave_policy.md] plus holidays [source: leave_policy.md]"
    assert extract_citations(text) == ["leave_policy.md"]


def test_enforce_citations_passthrough_when_cited():
    out = enforce_citations("You get 20 days [source: leave_policy.md]", True, ["leave_policy.md"])
    assert out.answer.startswith("You get 20 days")
    assert out.citations == ["leave_policy.md"]


def test_enforce_citations_appends_real_sources_when_model_forgot():
    out = enforce_citations("You get 20 days of PTO.", True, ["leave_policy.md"])
    assert "[source: leave_policy.md]" in out.answer
    assert out.citations == ["leave_policy.md"]


def test_enforce_citations_replaces_when_kb_empty():
    out = enforce_citations("Probably 30 days I guess?", True, [])
    assert out.answer == NOT_IN_HANDBOOK
    assert out.citations == []


def test_enforce_citations_ignores_non_kb_answers():
    out = enforce_citations("Nice to meet you!", False, [])
    assert out.answer == "Nice to meet you!"


# --------------------------------------------------------------------- PII

def test_redact_ssn_and_cards():
    text = "SSN 123-45-6789, card 4111 1111 1111 1111, account 123456789"
    red = redact_pii(text)
    assert "123-45-6789" not in red
    assert "4111 1111 1111 1111" not in red
    assert "123456789" not in red
    assert red.count("[redacted]") == 3


def test_redact_leaves_normal_numbers_alone():
    text = "Started 2026-07-06, $1,200 budget, 20 days PTO, ticket #42"
    assert redact_pii(text) == text
