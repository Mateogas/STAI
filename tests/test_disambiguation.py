from stai.handbook import build_handbook
from stai.models import HireProfile
from stai.policy import PolicyEngine
from stai.retriever import load_page_records


def test_confirmed_attribute_is_not_reasked(tmp_path):
    records = load_page_records(build_handbook(tmp_path).rag_pages_path)
    response = PolicyEngine(records).answer("Does ACC-006 apply to me?", HireProfile.alyssa())
    assert response.type == "grounded_answer"
    assert response.applicability == "does_not_apply"


def test_one_missing_constraining_attribute_asks_one_question_without_mutation(tmp_path):
    records = load_page_records(build_handbook(tmp_path).rag_pages_path)
    profile = HireProfile.alyssa().model_copy(update={"work_site": None})
    response = PolicyEngine(records).answer("Does ACC-006 apply to me?", profile)
    assert response.type == "clarification_request"
    assert response.question.count("?") == 1
    assert "work site" in response.question.lower()
