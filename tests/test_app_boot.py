from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[1] / "app.py"


def test_dialogue_workspace_boots_with_three_hire_destinations():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    assert not at.exception
    text = " ".join(item.value for item in at.markdown)
    assert "Ask AISHA" in text
    assert "Certificate Check" in text
    assert "History" in text
    assert "Active Handbook" in text
    assert "fictional educational" in text
    assert "Day 30 readiness" not in text


def test_hr_view_has_consent_only_records_and_privacy_empty_states():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    at.segmented_control[0].set_value("HR User")
    at.run()
    assert not at.exception
    text = " ".join(item.value for item in at.markdown)
    assert "Consented Escalation Cases" in text
    assert "Shared Validation Results" in text
    assert "Pending Attribute Change Requests" in text
    assert "private chat" in text.lower()

