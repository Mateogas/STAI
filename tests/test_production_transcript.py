"""Regression contract captured from the deployed production failure."""

from datetime import date
from pathlib import Path

from stai.handbook import build_handbook
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import Repo


def test_production_payroll_transcript_keeps_context_and_never_crosses_topic(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    artifacts = build_handbook(tmp_path / "handbook")
    service = AishaService(repo, load_page_records(artifacts.rag_pages_path))
    conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))

    turns = [
        service.send_message(conversation["id"], "Whats my payroll"),
        service.send_message(conversation["id"], "Well then how do i do the onboard"),
        service.send_message(conversation["id"], "How to i put my payroll details"),
        service.send_message(conversation["id"], "I need help in this"),
        service.send_message(conversation["id"], "route it please"),
        service.send_message(conversation["id"], "how does payroll work"),
    ]

    assert [turn.type for turn in turns] == [
        "grounded_answer",
        "escalation_offer",
        "escalation_offer",
        "escalation_offer",
        "escalation_confirmation",
        "grounded_answer",
    ]
    assert turns[0].citations[0].policy_id == "PAY-001"
    assert turns[1].citations[0].policy_id == "PAY-003"
    assert turns[2].citations[0].policy_id == "PAY-003"
    assert turns[3].topic.value == "payroll"
    assert turns[4].topic.value == "payroll"
    assert turns[5].citations[0].policy_id == "PAY-001"
    assert all(
        citation.policy_id.startswith("PAY-")
        for turn in turns
        for citation in turn.citations
    )
    assert repo.list_escalation_cases()[0]["topic"] == "payroll"


def test_turn_context_survives_service_restart(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    artifacts = build_handbook(tmp_path / "handbook")
    records = load_page_records(artifacts.rag_pages_path)
    service = AishaService(repo, records)
    conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))
    service.send_message(conversation["id"], "How do I update my payroll details?")

    restarted = AishaService(repo, records)
    offer = restarted.send_message(conversation["id"], "I need help with this")
    assert offer.type == "escalation_offer"
    assert offer.topic.value == "payroll"
    assert offer.route_owner == "Payroll Support"
