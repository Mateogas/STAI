from types import SimpleNamespace

from stai.guardrails import classify_input, parse_verdict, redact_pii, validate_policy_output


class FakeLLM:
    def __init__(self, reply): self.reply = reply
    def invoke(self, _messages): return SimpleNamespace(content=self.reply)


def test_classifier_parses_closed_categories_and_fails_open():
    assert parse_verdict('{"category":"off_topic"}').allowed is False
    assert parse_verdict('prefix {"category":"injection"} suffix').category == "injection"
    assert parse_verdict("garbage").allowed is True
    assert classify_input("payroll", llm=FakeLLM('{"category":"on_topic"}')).allowed


def test_classifier_failure_is_fail_open():
    class Boom:
        def invoke(self, _): raise ConnectionError("offline")
    assert classify_input("PAY-001", llm=Boom()).allowed


def test_malformed_or_unsupported_model_output_fails_closed():
    response = validate_policy_output("not json", set())
    assert response.type == "abstention" and response.citations == []


def test_citation_shaped_generated_text_is_not_trusted():
    raw = {
        "type": "grounded_answer", "text": "Claim [PAY-001 · AISHA Handbook v1.0 · p. 7]",
        "handbook_version": "1.0", "applicability": "applies", "evidence_state": "ready",
        "citations": [{"policy_id": "PAY-001", "handbook_version": "1.0", "page_start": 7}],
        "claims": [{"text": "Claim", "citation_indexes": [0]}],
    }
    assert validate_policy_output(raw, set()).type == "abstention"


def test_number_shaped_pii_is_redacted():
    output = redact_pii("SSN 123-45-6789 card 4111 1111 1111 1111")
    assert "123-45-6789" not in output and "4111" not in output
