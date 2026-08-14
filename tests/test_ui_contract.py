from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")


def test_accessibility_and_responsive_contract_is_explicit():
    assert "@media (max-width: 480px)" in SOURCE
    assert ":focus-visible" in SOURCE
    assert 'aria-live="polite"' in SOURCE
    assert 'role="status"' in SOURCE
    assert "min-height: 44px" in SOURCE


def test_ui_never_exposes_retrieval_or_medical_internals():
    forbidden_rendering = (
        "similarity_score", "reranking_score", "collection_name",
        "document_fingerprint", "ocr_text", "confidence_map",
    )
    for term in forbidden_rendering:
        assert f"st.write({term}" not in SOURCE
        assert f"st.markdown({term}" not in SOURCE


def test_selected_dialogue_information_hierarchy_is_present():
    for label in ("Ask AISHA", "Certificate Check", "History", "New Hire", "HR User"):
        assert label in SOURCE
    assert "persona picker" not in SOURCE.lower()


def test_conversation_and_nested_case_thread_contract_is_present():
    for label in (
        "New conversation",
        "Your conversations",
        "HR ticket thread",
        "Parent sharing is active",
        "Reply in this HR ticket thread",
        "Hire-visible reply",
        "HR-only note",
        "Resolution summary",
        "Resolution type",
        "Resolution scope",
        "Propose this clarification for broader reuse",
        "Ask AISHA about this HR resolution",
        "Approve clarification",
    ):
        assert label in SOURCE
    assert "active_case_id" in SOURCE
    assert "ticket_tree_" in SOURCE


def test_approved_dialogue_visual_contract_is_preserved():
    for token in (
        "--aisha-navy: #0a2450",
        "--aisha-blue: #0b4da2",
        "--aisha-gold: #c9962c",
        "--aisha-paper: #fffdfa",
        "--aisha-canvas: #f2efe8",
    ):
        assert token in SOURCE
    for shell_region in (
        "aisha_topbar",
        "dialogue_nav",
        "dialogue_chat",
        "dialogue_context",
        "aisha-brand",
        "aisha-logo",
    ):
        assert shell_region in SOURCE
    assert "st.columns([1.05, 3, 1.15]" in SOURCE
