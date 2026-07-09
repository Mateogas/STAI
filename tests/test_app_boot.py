"""Boot the real Streamlit script headlessly and assert it renders clean.

Catches import errors, bad st.* calls, and broken seed data without needing
Ollama or a browser (no chat message is sent, so no LLM call happens).
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def _values(elements) -> list[str]:
    return [element.value for element in elements]


def _rendered_text(at: AppTest) -> str:
    parts = []
    for elements in (at.header, at.subheader, at.caption, at.markdown):
        parts.extend(_values(elements))
    parts.extend(button.label for button in at.button)
    return "\n".join(parts)


def test_app_boots_new_hire_readiness_cockpit():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()

    assert not at.exception

    rendered = _rendered_text(at)
    assert "aisha-topbar" in rendered
    assert "aisha-demo-strip" in rendered
    assert "Day 30 readiness cockpit" in rendered
    assert "Goal" in rendered and "Day 30 readiness" in rendered
    assert "Next up" in rendered
    assert "Open tasks on your ramp plan" in rendered
    assert "Blocked · needs help" in rendered
    assert "Who can help" in rendered
    assert "aisha-chat-heading" in rendered
    assert "Knows your ramp plan and the handbook" in rendered
    assert "Fictionalized BDO educational capstone" in rendered
    assert '[data-testid="stChatMessage"]' in rendered
    assert len(at.selectbox) == 0
    assert len(at.segmented_control) == 1
    assert len(at.text_input) == 1
    assert {"Next task", "Day 30 readiness", "Who can help?"} <= {
        button.label for button in at.button
    }


def test_hr_persona_renders_privacy_first_support_console():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    at.segmented_control[0].set_value("hr_admin")
    at.run()

    assert not at.exception

    rendered = _rendered_text(at)
    assert _values(at.header) == ["People Experience · Support Console"]
    assert {"May need support", "Explicit help requests", "Pulse & support signals"} <= set(
        _values(at.subheader)
    )
    assert "Enough signal to offer help, not enough detail to police." in rendered
    assert "Signals are derived from tasks, pulse trends, and explicit help requests." in rendered
    assert "Privacy note: summary from tasks, pulse, and escalations." in rendered
    assert "No private chat transcript shown." in rendered
    assert len(at.dataframe) == 1
