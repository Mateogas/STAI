"""Observable contracts for AISHA's bounded observe-plan-act policy flow."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from stai.handbook import build_handbook
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import Repo


@pytest.fixture
def service(tmp_path: Path) -> AishaService:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    return AishaService(repo, records)


def ask(service: AishaService, prompt: str):
    conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    return service.send_message(conversation["id"], prompt)


@pytest.mark.parametrize(
    "prompt",
    [
        "Ok how do I get my payroll?",
        "Where do I get my payroll?",
    ],
)
def test_ambiguous_get_payroll_asks_about_the_hires_goal(service, prompt: str) -> None:
    response = ask(service, prompt)
    assert response.type == "clarification_request"
    assert response.choices == [
        "When will I be paid?",
        "Where can I view my payslip?",
        "How does payroll enrollment work?",
    ]


@pytest.mark.parametrize(
    "prompt",
    [
        "Which days do I get my payroll?",
        "When is my next payroll?",
        "When is the next payroll schedule?",
    ],
)
def test_payday_wording_retrieves_the_schedule_procedure(service, prompt: str) -> None:
    response = ask(service, prompt)
    assert response.type == "grounded_answer"
    assert response.citations[0].policy_id == "PAY-001"
    assert "semi-monthly" in response.text.lower()
    assert "15th" in response.text


def test_conversational_hr_catalog_is_scoped_and_runs_through_agent(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    service = AishaService(repo, records)
    response = ask(service, "What other HR policies could I ask about?")
    assert response.type == "grounded_answer"
    assert "**HR Policies**" in response.text
    assert "**Payroll**" not in response.text
    assert "**Resource Access**" not in response.text
    assert {citation.policy_id for citation in response.citations} == {
        *(f"HRP-{number:03d}" for number in range(1, 8)),
    }


def test_subject_policy_question_is_not_misclassified_as_catalog(service) -> None:
    response = ask(service, "What are the policies against using TikTok at work?")
    assert "**HR Policies**" not in response.text
    if response.citations:
        assert response.citations[0].policy_id == "ACC-004"


def test_production_social_media_wording_is_grounded_in_device_security(service) -> None:
    response = ask(
        service,
        "What policies are there against using personal social media accounts inside work laptops?",
    )
    assert response.type == "grounded_answer"
    assert response.citations[0].policy_id == "ACC-004"


@pytest.mark.parametrize(
    ("prompt", "policy_id"),
    [
        ("Where can I view my payslip?", "PAY-002"),
        ("What is gross pay versus net pay?", "PAY-004"),
        ("Can I take leave while I am probationary?", "HRP-002"),
        ("What happens if flooding or a typhoon makes me late?", "HRP-001"),
        ("Can HR see every conversation I have with AISHA?", "HRP-005"),
        ("Can I submit a photo of my medical certificate?", "HRP-004"),
        ("Can my manager ask me for my password?", "ACC-004"),
    ],
)
def test_representative_new_hire_questions_are_grounded_in_the_intended_policy(
    service, prompt: str, policy_id: str
) -> None:
    response = ask(service, prompt)
    assert response.type == "grounded_answer"
    assert response.citations[0].policy_id == policy_id


@pytest.mark.parametrize(
    "prompt",
    [
        "Is my onboarding training time paid?",
        "How will overtime and night work show on my pay?",
        "Do I get 13th-month pay if I joined in August?",
    ],
)
def test_uncovered_payroll_subjects_abstain_without_an_hr_offer(service, prompt: str) -> None:
    response = ask(service, prompt)
    assert response.type == "abstention"
    assert response.reason == "handbook_omission"
    assert response.citations == []


def test_partial_policy_evidence_can_offer_hr_without_creating_a_case(service) -> None:
    response = ask(service, "I entered the wrong bank account number. Can you fix it?")
    assert response.type == "escalation_offer"
    assert response.citations[0].policy_id == "PAY-003"
    assert service.repo.list_escalation_cases() == []
