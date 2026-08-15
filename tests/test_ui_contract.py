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
    for label in (
        "Ask AISHA", "Certificate Check", "History", "Alyssa · Hire", "HR · Support"
    ):
        assert label in SOURCE
    assert "persona picker" not in SOURCE.lower()


def test_first_view_states_purpose_scope_and_demo_boundary():
    for label in (
        "Reach the right onboarding rule, faster",
        "Payroll",
        "Resource Access",
        "HR Policies",
        "Fictional BDO educational demo",
        "No real employee data",
        "No BDO internal-system access",
        "Support, not surveillance",
    ):
        assert label in SOURCE
    for question in (
        "When will I receive my first pay?",
        "How do I request the systems I need?",
        "What should I do when I need sick leave?",
    ):
        assert question in SOURCE


def test_conversation_and_nested_case_thread_contract_is_present():
    for label in (
        "New conversation",
        "Your conversations",
        "HR support case",
        "Parent sharing is active",
        "Add information to this HR case",
        "Request one missing detail",
        "Ask through AISHA",
        "AISHA · case coordinator",
        "Offer direct human conversation",
        "Consent to direct HR conversation",
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


def test_outcome_consent_and_local_processing_states_are_explicit():
    for label in (
        "Handbook answer",
        "Your detail needed",
        "Insufficient handbook evidence",
        "Optional HR support",
        "Review before sharing",
        "Nothing has been shared yet",
        "I reviewed the summary and consent",
        "Checking the active handbook",
        "Local CPU processing can take a moment",
        "Handbook temporarily unavailable",
        "Reload assistant",
    ):
        assert label in SOURCE


def test_certificate_privacy_copy_hides_execution_internals():
    for label in (
        "Completeness check only",
        "Processed for this check",
        "Retained after a successful check",
        "No result was saved",
        "Official HR Document Route",
        "Blank Manual Field Summary",
    ):
        assert label in SOURCE
    assert "outcome.agent_execution" not in SOURCE


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
    assert "st.columns([1.1, 3.4, 1.15]" in SOURCE
