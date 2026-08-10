"""Persistent chat memory: chat_messages survive new Repo instances."""

from __future__ import annotations

from datetime import date

from stai.state import Repo


def test_policy_conversation_delete_cascades_messages_but_consented_case_survives(tmp_path):
    repo = Repo(tmp_path / "policy.db", secret_path=tmp_path / "key")
    conversation = repo.create_policy_conversation("emp-alyssa", date(2026, 8, 10))
    message = repo.add_policy_message(conversation["id"], "hire", "PAY-001 question")
    offer = repo.create_escalation_offer(
        conversation["id"], message["id"], "payroll", "Payroll Support",
        "Fictional HR Help Desk", "Clarify PAY-001 applicability.", ["PAY-001"],
    )
    case = repo.consent_escalation_offer(offer["offer_id"], expected_version=1)
    repo.delete_policy_conversation(conversation["id"])
    assert repo.list_policy_messages(conversation["id"]) == []
    assert repo.list_escalation_cases()[0]["case_id"] == case["case_id"]


def test_chat_message_roundtrip(repo):
    repo.add_chat_message("emp-alyssa", "assistant", "Hi Alyssa!", kind="checkin")
    repo.add_chat_message(
        "emp-alyssa",
        "assistant",
        "Leave is filed in the portal [source: leave_policy.md]",
        sources=[{"source": "leave_policy.md", "title": "Leave", "snippet": "..."}],
    )
    msgs = repo.list_chat_messages("emp-alyssa")
    assert len(msgs) == 2
    assert msgs[0].kind == "checkin" and msgs[0].sources == []
    assert msgs[1].sources[0]["source"] == "leave_policy.md"


def test_chat_memory_survives_repo_restart(repo):
    repo.add_chat_message("emp-alyssa", "user", "what is my Day 30 Readiness Check?")
    repo.add_chat_message("emp-alyssa", "assistant", "Here is your plan...")

    reopened = Repo(repo.db_path)  # same SQLite file, fresh instance
    msgs = reopened.list_chat_messages("emp-alyssa")
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].content == "what is my Day 30 Readiness Check?"


def test_chat_memory_is_per_employee(repo):
    repo.add_chat_message("emp-alyssa", "user", "hello from Alyssa")
    repo.add_chat_message("emp-jomar", "user", "hello from Jomar")
    assert len(repo.list_chat_messages("emp-alyssa")) == 1
    assert repo.list_chat_messages("emp-jomar")[0].content == "hello from Jomar"


def test_list_chat_messages_limit_keeps_most_recent(repo):
    for i in range(5):
        repo.add_chat_message("emp-alyssa", "user", f"message {i}")
    last_two = repo.list_chat_messages("emp-alyssa", limit=2)
    assert [m.content for m in last_two] == ["message 3", "message 4"]


def test_clear_chat_messages(repo):
    repo.add_chat_message("emp-alyssa", "user", "hello")
    repo.add_chat_message("emp-jomar", "user", "hello")
    assert repo.clear_chat_messages("emp-alyssa") == 1
    assert repo.list_chat_messages("emp-alyssa") == []
    assert len(repo.list_chat_messages("emp-jomar")) == 1
