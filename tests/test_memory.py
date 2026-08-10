from datetime import date

from stai.state import Repo


def test_policy_memory_survives_restart_and_delete_cascades_messages(tmp_path):
    path = tmp_path / "policy.db"; key = tmp_path / "key"
    repo = Repo(path, secret_path=key)
    conversation = repo.create_policy_conversation("emp-alyssa", date(2026, 8, 10))
    repo.add_policy_message(conversation["id"], "hire", "PAY-001 question")
    reopened = Repo(path, secret_path=key)
    assert reopened.list_policy_messages(conversation["id"])[0]["text"] == "PAY-001 question"
    assert reopened.delete_policy_conversation(conversation["id"])
    assert reopened.list_policy_messages(conversation["id"]) == []


def test_consented_case_survives_conversation_delete(tmp_path):
    repo = Repo(tmp_path / "policy.db", secret_path=tmp_path / "key")
    conversation = repo.create_policy_conversation("emp-alyssa", date(2026, 8, 10))
    message = repo.add_policy_message(conversation["id"], "hire", "PAY-001 question")
    offer = repo.create_escalation_offer(conversation["id"], message["id"], "payroll", "Payroll Support", "Fictional HR Help Desk", "Clarify PAY-001 applicability.", ["PAY-001"])
    case = repo.consent_escalation_offer(offer["offer_id"], expected_version=1)
    repo.delete_policy_conversation(conversation["id"])
    assert repo.get_escalation_case(case["case_id"])["status"] == "open"
