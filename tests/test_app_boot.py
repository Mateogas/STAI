"""Boot the real Streamlit script headlessly and assert it renders clean.

Catches import errors, bad st.* calls, and broken seed data without needing
Ollama or a browser (no chat message is sent, so no LLM call happens).
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_app_boots_new_hire_view():
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    assert not at.exception
    assert at.title or at.header  # sidebar title + view header rendered
