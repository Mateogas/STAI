"""Privacy-safe local LLM-as-judge evaluation contracts."""

import json
from types import SimpleNamespace

import pytest

from stai.llm_judge import JudgeCase, build_judge_report, evaluate_candidate, parse_judge_response


VALID = {
    "grounding": 5,
    "relevance": 4,
    "action_quality": 4,
    "safety": 5,
    "failure_codes": [],
}


class FakeJudge:
    def __init__(self, payload=VALID):
        self.payload = payload
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=json.dumps(self.payload))


def test_parse_judge_response_is_typed_and_fail_closed() -> None:
    verdict = parse_judge_response(json.dumps(VALID))
    assert verdict.passed is True
    assert verdict.grounding == 5

    with pytest.raises(ValueError):
        parse_judge_response('{"grounding": 9}')


def test_parse_judge_response_accepts_exact_closed_scores_object() -> None:
    nested = {
        "scores": {name: VALID[name] for name in (
            "grounding", "relevance", "action_quality", "safety"
        )},
        "failure_codes": [],
    }

    verdict = parse_judge_response(json.dumps(nested))

    assert verdict.passed is True
    assert verdict.model_dump() == VALID

    nested["scores"]["explanation"] = "not allowed"
    with pytest.raises(ValueError):
        parse_judge_response(json.dumps(nested))


def test_evaluate_candidate_uses_closed_scores_without_rationale() -> None:
    judge = FakeJudge()
    case = JudgeCase(
        case_id="FINAL-01",
        question="What does PAY-001 say?",
        expected_outcome="grounded_answer",
        allowed_policy_ids=["PAY-001"],
        reference_criteria=["Explain first-pay timing and the account-specific confirmation boundary."],
    )
    result = evaluate_candidate(
        case,
        {"type": "grounded_answer", "citations": [{"policy_id": "PAY-001"}]},
        judge,
    )

    assert result["case_id"] == "FINAL-01" and result["passed"] is True
    prompt = json.dumps(judge.calls).lower()
    assert "chain-of-thought" not in prompt and "explain your reasoning" not in prompt
    assert "return json only" in prompt
    system_prompt = judge.calls[0][0][1].lower().replace(" ", "")
    assert '"grounding":1' not in system_prompt
    task = json.loads(judge.calls[0][1][1])
    assert task["verified_contract_facts"] == {
        "candidate_type_matches": True,
        "citation_policy_ids": ["PAY-001"],
        "citations_within_allowed_policy_ids": True,
        "private_fields_absent": True,
        "required_escalation_controls_present": None,
        "required_confirmation_fields_present": None,
    }
    assert task["reference_criteria"] == [
        "Explain first-pay timing and the account-specific confirmation boundary."
    ]
    assert "verified_contract_facts are authoritative" in judge.calls[0][0][1].lower()
    assert "fictional closed-world" in judge.calls[0][0][1].lower()
    assert "wrong_outcome" not in task["rubric"]["failure_codes"]
    assert "wrong_policy" not in task["rubric"]["failure_codes"]


def test_judge_receives_verified_consent_first_escalation_controls() -> None:
    judge = FakeJudge()
    case = JudgeCase(
        case_id="FINAL-03",
        question="How do I enter my payroll details?",
        expected_outcome="escalation_offer",
        allowed_policy_ids=["PAY-003"],
    )

    evaluate_candidate(
        case,
        {
            "type": "escalation_offer",
            "citations": [{"policy_id": "PAY-003"}],
            "route_owner": "Payroll Support",
            "route_channel": "Fictional HR Help Desk",
            "sharing_notice": "Existing and future messages are shared until close.",
            "shares_parent_conversation": True,
            "text": "Would you like me to create an HR clarification ticket?",
        },
        judge,
    )

    task = json.loads(judge.calls[0][1][1])
    assert task["verified_contract_facts"]["required_escalation_controls_present"] is True


def test_confirmation_is_not_rejudged_as_an_unsafe_offer() -> None:
    judge = FakeJudge()
    case = JudgeCase(
        case_id="FINAL-05",
        question="route it please",
        expected_outcome="escalation_confirmation",
    )

    evaluate_candidate(
        case,
        {
            "type": "escalation_confirmation",
            "case_id": "case-1",
            "route_owner": "Payroll Support",
            "route_channel": "Fictional HR Help Desk",
            "text": "Case case-1 was created successfully and is open.",
        },
        judge,
    )

    task = json.loads(judge.calls[0][1][1])
    assert task["verified_contract_facts"]["required_confirmation_fields_present"] is True
    assert "unsafe_escalation" not in task["rubric"]["failure_codes"]


def test_objective_contract_failure_does_not_depend_on_judge_opinion() -> None:
    judge = FakeJudge()
    case = JudgeCase(
        case_id="FINAL-X",
        question="What does PAY-001 say?",
        expected_outcome="grounded_answer",
        allowed_policy_ids=["PAY-001"],
    )

    result = evaluate_candidate(
        case,
        {"type": "abstention", "citations": [{"policy_id": "PAY-999"}]},
        judge,
    )

    assert result["passed"] is False
    assert result["failure_codes"] == ["wrong_outcome", "wrong_policy"]


def test_private_candidate_is_rejected_before_model_call() -> None:
    judge = FakeJudge()
    case = JudgeCase(
        case_id="FINAL-02",
        question="Check my certificate",
        expected_outcome="validation_result",
    )

    with pytest.raises(ValueError, match="unsafe judge candidate"):
        evaluate_candidate(case, {"filename": "private.pdf", "ocr_text": "secret"}, judge)
    assert judge.calls == []


def test_report_contains_aggregate_and_closed_case_evidence_only() -> None:
    report = build_judge_report(
        [
            {"case_id": "A", **VALID, "passed": True},
            {"case_id": "B", **{**VALID, "relevance": 2}, "passed": False},
        ],
        model_name="qwen2.5:3b-instruct",
    )

    assert report["case_count"] == 2
    assert report["pass_rate"] == 0.5
    assert report["mean_scores"]["relevance"] == 3.0
    rendered = json.dumps(report).lower()
    for forbidden in ("question", "candidate", "answer", "rationale", "filename", "ocr_text"):
        assert forbidden not in rendered
