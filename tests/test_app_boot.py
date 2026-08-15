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
    assert "Reach the right onboarding rule, faster" in text
    assert "Support, not surveillance" in text
    assert any("When will I receive my first pay?" in button.label for button in at.button)
    assert "Day 30 readiness" not in text


def test_hr_view_has_consent_only_records_and_privacy_empty_states():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    at.segmented_control[0].set_value("HR · Support")
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
    assert any("View evidence" in expander.label for expander in at.expander)


def test_certificate_check_requires_privacy_acknowledgement_before_processing():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    at.radio[0].set_value("Certificate Check")
    at.run()
    assert not at.exception
    text = " ".join(item.value for item in at.markdown)
    assert "Processed for this check" in text
    assert "Retained after a successful check" in text
    run_check = next(button for button in at.button if button.label == "Run private local check")
    assert run_check.disabled


def test_streamlit_consent_button_shows_persisted_case_confirmation():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    at.chat_input[0].set_value("Where is the official payroll route?")
    at.run()
    review = next(
        checkbox for checkbox in at.checkbox
        if checkbox.label.startswith("I reviewed the summary")
    )
    review.set_value(True)
    at.run()
    consent = next(button for button in at.button if button.label == "Consent and create case")
    assert not consent.disabled
    consent.click()
    at.run()
    assert not at.exception
    text = " ".join(item.value for item in at.markdown)
    assert "created successfully" in text
    assert any("Case reference:" in item.value for item in at.success)
    assert any("HR case" in button.label for button in at.button)

    open_thread = next(button for button in at.button if button.label == "Open HR case thread")
    open_thread.click()
    at.run()
    assert not at.exception
    thread_text = " ".join(item.value for item in at.markdown)
    assert "Parent sharing is active" in thread_text
    assert "HR support case" in thread_text
