from pathlib import Path

from stai.handbook import build_handbook
from stai.models import ApplicabilityStatus, HireProfile
from stai.policy import PolicyEngine, evaluate_applicability
from stai.retriever import load_page_records


def records(tmp_path: Path):
    return load_page_records(build_handbook(tmp_path).rag_pages_path)


def policy_record(rows, policy_id):
    return next(row for row in rows if row.policy_id == policy_id and row.page_kind == "policy")


def test_nine_anchor_applicability_semantics(tmp_path: Path) -> None:
    rows = records(tmp_path)
    alyssa = HireProfile.alyssa()
    assert evaluate_applicability(policy_record(rows, "PAY-001"), alyssa).status == ApplicabilityStatus.APPLIES
    assert evaluate_applicability(policy_record(rows, "PAY-006"), alyssa).status == ApplicabilityStatus.DOES_NOT_APPLY
    assert evaluate_applicability(policy_record(rows, "ACC-001"), alyssa).status == ApplicabilityStatus.APPLIES
    assert evaluate_applicability(policy_record(rows, "ACC-006"), alyssa).status == ApplicabilityStatus.DOES_NOT_APPLY
    assert evaluate_applicability(policy_record(rows, "HRP-001"), alyssa).status == ApplicabilityStatus.APPLIES
    assert evaluate_applicability(policy_record(rows, "HRP-007"), alyssa).status == ApplicabilityStatus.DOES_NOT_APPLY


def test_missing_constraining_fact_asks_one_focused_question(tmp_path: Path) -> None:
    rows = records(tmp_path)
    uncertain = HireProfile.alyssa().model_copy(update={"work_site": None})
    response = PolicyEngine(rows).answer("Does ACC-006 apply to me?", uncertain)
    assert response.type == "clarification_request"
    assert response.applicability == ApplicabilityStatus.NEEDS_CLARIFICATION
    assert "work site" in response.question.lower()
    assert len(response.choices) <= 4


def test_grounded_answer_uses_active_policy_page_citation(tmp_path: Path) -> None:
    response = PolicyEngine(records(tmp_path)).answer("What does PAY-001 say?", HireProfile.alyssa())
    assert response.type == "grounded_answer"
    assert response.citations[0].policy_id == "PAY-001"
    assert response.citations[0].handbook_version == "1.0"
    assert response.citations[0].render() in response.text
    assert "Based on AISHA Handbook v1.0." in response.text


def test_unsupported_question_abstains_without_related_citation(tmp_path: Path) -> None:
    response = PolicyEngine(records(tmp_path)).answer("What is the company cryptocurrency policy?", HireProfile.alyssa())
    assert response.type == "abstention"
    assert response.citations == []
    assert response.reason == "insufficient_evidence"

