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


def test_streamlit_ask_uses_topic_safe_turn_engine():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    at.chat_input[0].set_value("how does payroll work")
    at.run()
    assert not at.exception
    text = " ".join(item.value for item in at.markdown)
    assert "PAY-001" in text
    assert "ACC-005" not in text


def test_streamlit_consent_button_shows_persisted_case_confirmation():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    at.chat_input[0].set_value("Connect me with payroll support")
    at.run()
    consent = next(button for button in at.button if button.label == "Consent and create case")
    consent.click()
    at.run()
    assert not at.exception
    text = " ".join(item.value for item in at.markdown)
    assert "created successfully" in text
    assert any("Case reference:" in item.value for item in at.success)
    assert any("HR ticket" in button.label for button in at.button)

    open_thread = next(button for button in at.button if button.label == "Open HR ticket thread")
    open_thread.click()
    at.run()
    assert not at.exception
    thread_text = " ".join(item.value for item in at.markdown)
    assert "Parent sharing is active" in thread_text
    assert "HR ticket thread" in thread_text
