"""AISHA Dialogue workspace for the fictional educational onboarding demo."""

from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from stai.handbook import build_handbook
from stai.models import ApplicabilityStatus
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import Repo


DEMO_DATE = date(2026, 8, 10)
DISCLAIMER = (
    "AISHA is a fictional educational capstone prototype. It is not affiliated "
    "with, endorsed by, or representative of BDO Unibank. All people, records, "
    "policies, and interactions shown here are fictionalized."
)

# These tokens and the Dialogue shell mirror the approved Variant A prototype.
CSS = """
<style>
:root {
  color-scheme: light;
  --aisha-navy: #0a2450;
  --aisha-blue: #0b4da2;
  --aisha-gold: #c9962c;
  --aisha-ink: #15223a;
  --aisha-muted: #657083;
  --aisha-paper: #fffdfa;
  --aisha-canvas: #f2efe8;
  --aisha-line: #dedbd2;
  --aisha-soft-blue: #e9f0fb;
  --aisha-soft-gold: #fff4d8;
  --aisha-soft-green: #e8f4eb;
  --aisha-green: #28683e;
}
* { box-sizing: border-box; }
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background: var(--aisha-canvas);
  color: var(--aisha-ink);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu { display: none !important; }
[data-testid="stSidebar"] { display: none !important; }
.block-container { max-width: 1220px; padding: 1rem 1rem 1.5rem; }
h1, h2, h3, p, li, label, [data-testid="stMarkdownContainer"] { color: var(--aisha-ink); }
button, input, textarea { font: inherit; }
button { cursor: pointer; }
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible,
[role="radio"]:focus-visible, [data-testid="stFileUploaderDropzone"]:focus-visible {
  outline: 3px solid #58a6ff !important;
  outline-offset: 2px !important;
}
[data-testid="stAppViewContainer"] button,
[data-testid="stFileUploaderDropzone"] { min-height: 44px !important; }

/* Full-width approved navy header. */
.st-key-aisha_topbar {
  width: 100vw;
  margin: -1rem calc(50% - 50vw) 1.35rem;
  padding: .62rem max(1.25rem, calc((100vw - 1220px) / 2 + 1rem));
  background: var(--aisha-navy);
  color: white;
  box-shadow: 0 2px 12px rgba(10, 36, 80, .16);
}
.aisha-brand { display: flex; align-items: center; gap: 10px; min-height: 48px; color: white; }
.aisha-logo {
  display: grid; place-items: center; flex: 0 0 38px; width: 38px; height: 38px;
  border-radius: 10px; background: var(--aisha-gold); color: var(--aisha-navy);
  font-size: 18px; font-weight: 850;
}
.aisha-brand strong, .aisha-identity strong { display: block; color: white; }
.aisha-brand small, .aisha-identity span { display: block; color: #aebbd4; font-size: 11px; }
.aisha-identity { min-height: 42px; padding: 4px 0 4px 16px; border-left: 1px solid rgba(255,255,255,.18); }
.st-key-aisha_topbar [data-testid="stButtonGroup"] { justify-content: center; }
.st-key-aisha_topbar [data-testid="stButtonGroup"] > div {
  padding: 4px; border-radius: 10px; background: rgba(255,255,255,.09);
}
.st-key-aisha_topbar [data-testid="stButtonGroup"] button { color: #dce5f5; border: 0; background: transparent; }
.st-key-aisha_topbar [data-testid="stButtonGroup"] button p { color: #dce5f5; }
.st-key-aisha_topbar [data-testid="stButtonGroup"] button[data-selected="true"] {
  background: white !important; color: var(--aisha-navy) !important; font-weight: 750;
}
.st-key-aisha_topbar [data-testid="stButtonGroup"] button[data-selected="true"] p { color: var(--aisha-navy); }

/* Shared paper-card language. */
.st-key-dialogue_nav, .st-key-dialogue_chat, .st-key-dialogue_context,
.st-key-hr_nav, .st-key-hr_detail {
  height: 100%; min-height: 650px; overflow: hidden;
  border: 1px solid var(--aisha-line) !important;
  border-radius: 14px !important;
  background: var(--aisha-paper) !important;
  box-shadow: 0 5px 20px rgba(10,36,80,.05);
}
.st-key-dialogue_nav, .st-key-dialogue_context, .st-key-hr_nav { padding: 18px; }
.st-key-dialogue_chat, .st-key-hr_detail { padding: 0; }
.aisha-eyebrow {
  margin: 0 0 6px; color: var(--aisha-blue); font-size: 11px; font-weight: 800;
  letter-spacing: .08em; text-transform: uppercase;
}
.aisha-muted { color: var(--aisha-muted); }
.aisha-small { font-size: 12px; }
.aisha-profile-block { padding-bottom: 15px; border-bottom: 1px solid var(--aisha-line); }
.aisha-profile-block strong { display: block; color: var(--aisha-ink); }

/* Left destination rail. */
.st-key-dialogue_nav [data-testid="stRadio"], .st-key-hr_nav [data-testid="stRadio"] { margin-top: .6rem; }
.st-key-dialogue_nav [data-testid="stRadio"] > div, .st-key-hr_nav [data-testid="stRadio"] > div { gap: 6px; }
.st-key-dialogue_nav [role="radiogroup"] label, .st-key-hr_nav [role="radiogroup"] label {
  width: 100%; min-height: 44px; margin: 0; padding: 10px 11px;
  border-radius: 9px; color: var(--aisha-ink); transition: background .15s ease;
}
.st-key-dialogue_nav [data-testid="stRadioOption"][data-selected="true"],
.st-key-hr_nav [data-testid="stRadioOption"][data-selected="true"] {
  background: var(--aisha-soft-blue); color: var(--aisha-blue); font-weight: 750;
}
.st-key-dialogue_nav [data-testid="stRadioOption"] > div > div > div:first-child,
.st-key-hr_nav [data-testid="stRadioOption"] > div > div > div:first-child { display: none; }
.st-key-dialogue_nav [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p,
.st-key-hr_nav [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p { font-size: 13px; }

/* Central dialogue surface. */
.aisha-chat-head { padding: 18px 20px 14px; border-bottom: 1px solid var(--aisha-line); }
.aisha-chat-head h1, .aisha-chat-head h2 { margin: 0; color: var(--aisha-ink); font-size: 20px; }
.aisha-topic-line { margin-top: 6px; color: var(--aisha-muted); font-size: 12px; }
.st-key-dialogue_chat > div[data-testid="stVerticalBlock"] { min-height: 648px; }
.st-key-dialogue_chat [data-testid="stChatMessage"] {
  width: calc(100% - 2rem); margin: .75rem 1rem 0; padding: .75rem .9rem;
  border: 1px solid var(--aisha-line); border-radius: 13px; background: white;
}
.st-key-dialogue_chat [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
  width: min(82%, calc(100% - 2rem)); margin-left: auto; background: var(--aisha-soft-blue);
  border-color: #c9d8ef;
}
.st-key-dialogue_chat [data-testid="stChatInput"] {
  margin: 1rem; border-top: 1px solid var(--aisha-line); background: white;
}
.st-key-dialogue_chat [data-testid="stChatInput"] > div,
.st-key-dialogue_chat [data-testid="stChatInput"] > div > div,
.st-key-dialogue_chat [data-testid="stChatInput"] textarea {
  border-color: #aab2bf !important; background: white !important; color: var(--aisha-ink) !important;
}
.st-key-dialogue_chat [data-testid="stChatInput"] textarea::placeholder { color: var(--aisha-muted); opacity: 1; }
.aisha-empty { margin: 1rem; padding: 1rem; border-radius: 11px; background: #faf9f5; color: var(--aisha-muted); }
.aisha-outcome {
  display: inline-flex; align-items: center; gap: 6px; margin-bottom: 6px; padding: 5px 8px;
  border-radius: 999px; background: var(--aisha-soft-blue); color: #17477e;
  font-size: 11px; font-weight: 750;
}
.aisha-outcome.warn { background: var(--aisha-soft-gold); color: #6d5000; }
.aisha-outcome.good { background: var(--aisha-soft-green); color: var(--aisha-green); }
.aisha-outcome.neutral { background: #eceff3; color: #45546a; }
[data-testid="stExpander"] { border-color: var(--aisha-line) !important; background: #faf9f5; }

/* Context rail and structured detail cards. */
.aisha-context-list { display: grid; gap: 10px; }
.aisha-context-item, .aisha-record {
  padding: 11px; border: 1px solid transparent; border-radius: 10px; background: #f5f2eb;
}
.aisha-context-item span, .aisha-context-item strong { display: block; }
.aisha-context-item span { color: var(--aisha-muted); font-size: 11px; }
.aisha-context-item strong { margin-top: 2px; color: var(--aisha-ink); font-size: 13px; }
.aisha-privacy-box {
  margin-top: 12px; padding: 12px; border-radius: 10px;
  background: var(--aisha-soft-green); color: #28583a; font-size: 12px; line-height: 1.45;
}
.aisha-detail-head { padding: 22px 22px 10px; }
.aisha-detail-head h1 { margin: 4px 0 8px; font-size: clamp(24px, 3vw, 34px); }
.aisha-detail-body { padding: 0 22px 22px; }
.aisha-fact-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; margin: 12px 0; }
.aisha-fact { min-width: 0; padding: 10px; border-radius: 9px; background: #f2f4f7; overflow-wrap: anywhere; }
.aisha-fact span { display: block; color: var(--aisha-muted); font-size: 11px; }
.aisha-record { margin: .75rem 0; background: #faf9f5; border-color: var(--aisha-line); }
.aisha-record-title { margin: 5px 0; color: var(--aisha-ink); font-weight: 750; }
.aisha-status-note {
  margin: .75rem 1rem; padding: .7rem .85rem; border-left: 4px solid var(--aisha-blue);
  border-radius: 0 8px 8px 0; background: var(--aisha-soft-blue);
}
.aisha-disclaimer { max-width: 800px; margin: 24px auto 0; color: var(--aisha-muted); font-size: 11px; text-align: center; }
.aisha-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }

.stButton > button { border: 1px solid #9ca8b9; border-radius: 9px; background: white; color: var(--aisha-ink); }
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  border-color: var(--aisha-blue) !important; background: var(--aisha-blue) !important; color: white !important;
}
.stButton > button:hover { border-color: var(--aisha-gold); color: var(--aisha-navy); }
[data-testid="stFileUploaderDropzone"] { border-color: #9aa5b5; background: #fbfaf7; }

@media (max-width: 900px) {
  .st-key-dialogue_context { display: none; }
  .st-key-dialogue_nav, .st-key-dialogue_chat, .st-key-hr_nav, .st-key-hr_detail { min-height: 600px; }
  .aisha-fact-grid { grid-template-columns: 1fr; }
}
@media (max-width: 650px) {
  .block-container { padding: .5rem .55rem 1.25rem; }
  .st-key-aisha_topbar { margin-top: -.5rem; margin-bottom: .65rem; padding: .6rem .75rem; }
  .st-key-aisha_topbar [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  .st-key-aisha_topbar [data-testid="column"] { min-width: calc(50% - .5rem) !important; }
  .st-key-aisha_topbar [data-testid="column"]:nth-child(2) { order: 3; min-width: 100% !important; }
  .aisha-identity { text-align: right; }
  div[data-testid="stHorizontalBlock"]:has(.st-key-dialogue_nav),
  div[data-testid="stHorizontalBlock"]:has(.st-key-hr_nav) { flex-wrap: wrap; }
  div[data-testid="stHorizontalBlock"]:has(.st-key-dialogue_nav) > div[data-testid="column"],
  div[data-testid="stHorizontalBlock"]:has(.st-key-hr_nav) > div[data-testid="column"] { min-width: 100% !important; }
  .st-key-dialogue_nav, .st-key-hr_nav { min-height: auto; padding: 10px; }
  .st-key-dialogue_nav .aisha-profile-block, .st-key-hr_nav .aisha-profile-block { display: none; }
  .st-key-dialogue_nav [role="radiogroup"], .st-key-hr_nav [role="radiogroup"] { flex-direction: row; gap: 4px !important; }
  .st-key-dialogue_nav [role="radiogroup"] label, .st-key-hr_nav [role="radiogroup"] label {
    flex: 1; justify-content: center; padding: 8px 4px; text-align: center;
  }
  .st-key-dialogue_nav [role="radiogroup"] label > div:first-child,
  .st-key-hr_nav [role="radiogroup"] label > div:first-child { display: none; }
  .st-key-dialogue_chat, .st-key-hr_detail { min-height: 560px; }
  .st-key-dialogue_chat [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) { width: 94%; }
}
@media (max-width: 480px) {
  .aisha-brand small { display: none; }
  .st-key-dialogue_chat, .st-key-hr_detail { min-height: 520px; }
}
</style>
"""


@st.cache_resource
def get_repo() -> Repo:
    return Repo()


@st.cache_resource
def get_service() -> AishaService:
    artifacts = build_handbook()
    return AishaService(get_repo(), load_page_records(artifacts.rag_pages_path))


def announce(message: str) -> None:
    st.markdown(
        f'<div role="status" aria-live="polite" class="aisha-status-note">{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def outcome_badge(response_type: str | None) -> None:
    labels = {
        "grounded_answer": ("Grounded answer", "good"),
        "clarification_request": ("Needs your answer", "warn"),
        "abstention": ("Unable to answer safely", "neutral"),
        "escalation_offer": ("Human support available", "warn"),
    }
    label, tone = labels.get(response_type or "", ("AISHA", ""))
    st.markdown(
        f'<span class="aisha-outcome {tone}">{escape(label)}</span>',
        unsafe_allow_html=True,
    )


def evidence_area(response) -> None:
    if not response.citations:
        return
    with st.expander("Evidence", expanded=False):
        for citation in response.citations:
            page = (
                f"p. {citation.page_start}"
                if not citation.page_end
                else f"pp. {citation.page_start}-{citation.page_end}"
            )
            st.markdown(
                f"- **{citation.policy_id}** · revision 1 · AISHA Handbook "
                f"v{citation.handbook_version} · {page} · active artifact"
            )


def ensure_conversation(service: AishaService) -> str:
    conversation_id = st.session_state.get("conversation_id")
    if conversation_id and service.repo.get_policy_conversation(conversation_id):
        return conversation_id
    created = service.create_conversation("emp-alyssa", DEMO_DATE)
    st.session_state.conversation_id = created["id"]
    return created["id"]


def render_topbar() -> str:
    with st.container(key="aisha_topbar"):
        brand, switch, identity = st.columns([1.15, 1, 1], vertical_alignment="center")
        with brand:
            st.markdown(
                '<div class="aisha-brand"><span class="aisha-logo">A</span><div>'
                '<strong>AISHA</strong><small>AI Support for Hires and Associates</small>'
                "</div></div>",
                unsafe_allow_html=True,
            )
        with switch:
            role = st.segmented_control(
                "View as",
                ["New Hire", "HR User"],
                default="New Hire",
                key="role_view",
                label_visibility="collapsed",
                width="stretch",
            )
        with identity:
            if role == "HR User":
                name, detail = "HR User", "Fictional support workspace"
            else:
                name, detail = "Alyssa Reyes", "Branch Banking Associate"
            st.markdown(
                f'<div class="aisha-identity"><strong>{name}</strong><span>{detail}</span></div>',
                unsafe_allow_html=True,
            )
    return role or "New Hire"


def render_context(repo: Repo) -> None:
    profile = repo.get_hire_profile("emp-alyssa")
    st.markdown('<p class="aisha-eyebrow">Current context</p>', unsafe_allow_html=True)
    st.markdown(
        "<div class='aisha-context-list'>"
        "<div class='aisha-context-item'><span>Profile</span>"
        f"<strong>{escape(profile.employment_classification.title())} · "
        f"{escape(profile.work_site.replace('_', ' ').title())}</strong></div>"
        "<div class='aisha-context-item'><span>Support boundary</span>"
        "<strong>No automatic profile changes or escalation</strong></div>"
        "<div class='aisha-context-item'><span>Sources</span>"
        "<strong>Policy metadata only</strong></div>"
        "<div class='aisha-context-item'><span>Simulated date</span>"
        f"<strong>{DEMO_DATE.strftime('%B %d, %Y')}</strong></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="aisha-privacy-box">Confirmed Hire Profile attributes decide '
        "applicability. Conversation claims never overwrite them.</div>",
        unsafe_allow_html=True,
    )


def ask_aisha(service: AishaService) -> None:
    st.markdown(
        '<div class="aisha-chat-head"><p class="aisha-eyebrow">Dialogue</p>'
        "<h2>Ask safely, then act with confidence</h2>"
        '<div class="aisha-topic-line">Payroll · Resource Access · HR Policies</div></div>',
        unsafe_allow_html=True,
    )
    conversation_id = ensure_conversation(service)
    messages = service.list_messages(conversation_id)
    if not messages:
        st.markdown(
            '<div class="aisha-empty"><strong>Start with an onboarding question.</strong><br>'
            "AISHA checks the active handbook, your confirmed profile, and the evidence "
            "needed for a safe answer.</div>",
            unsafe_allow_html=True,
        )
    for message in messages:
        role = "user" if message["role"] == "hire" else "assistant"
        with st.chat_message(role):
            if role == "assistant":
                outcome_badge(message.get("response_type"))
            st.markdown(message["text"])

    prompt = st.chat_input("Ask about Payroll, Resource Access, or HR Policies")
    if not prompt:
        return
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.status("Checking the active handbook…", expanded=False):
        response = service.send_message(conversation_id, prompt)
    announce(f"AISHA returned {response.type.replace('_', ' ')}.")
    with st.chat_message("assistant"):
        outcome_badge(response.type)
        st.markdown(response.text)
        evidence_area(response)
        if response.type == "escalation_offer":
            st.markdown(
                "**Nothing has been shared yet.** If you consent, HR will receive only "
                f"this summary: “{response.proposed_summary}”\n\n"
                f"Route: {response.route_owner} · {response.route_channel}"
            )
            if st.button(
                "Consent and create case",
                key=f"consent-{response.offer_id}",
                type="primary",
            ):
                service.consent_escalation(response.offer_id, expected_version=response.version)
                announce("Your consented escalation case was created.")


def certificate_check(service: AishaService) -> None:
    st.markdown(
        '<div class="aisha-chat-head"><p class="aisha-eyebrow">Certificate check</p>'
        "<h2>Run a private local completeness check</h2>"
        '<div class="aisha-topic-line">HRP-004 · AISHA Handbook v1.0 · pp. 78–85</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="aisha-privacy-box" style="margin:1rem">Local completeness only—not '
        "authenticity, approval, medical assessment, diagnosis, or submission. Processing "
        "stays local; rejected or failed checks create no result.</div>",
        unsafe_allow_html=True,
    )
    st.caption("Accepted: one PDF, JPG, or PNG · up to 10 MB · PDF up to 3 pages · local extraction/OCR")
    acknowledged = st.checkbox(
        "I understand the file and extracted text are discarded; AISHA stores only the safe result."
    )
    upload = st.file_uploader("Certificate file", type=["pdf", "png", "jpg", "jpeg"])
    if not st.button(
        "Run local completeness check",
        disabled=upload is None or not acknowledged,
        type="primary",
    ):
        st.info("The original belongs in the separate fictional Official HR Document Route.")
        return
    with st.status("Extracting locally, validating, and cleaning up…", expanded=False):
        outcome = service.medical.check(
            upload.getvalue(),
            filename=upload.name,
            evaluation_date=DEMO_DATE,
            applicability=ApplicabilityStatus.APPLIES,
            acknowledged=acknowledged,
        )
    announce(f"Certificate Check outcome: {outcome.kind.replace('_', ' ')}.")
    if outcome.kind == "validation_result":
        status = (outcome.status or "complete").replace("_", " ").title()
        st.success(status)
        codes = outcome.missing_codes + outcome.inconsistency_codes + outcome.review_codes
        if codes:
            st.markdown("**Result details**")
            for code in codes:
                st.markdown(f"- {code.replace('_', ' ').title()}")
    elif outcome.kind == "retry_required":
        st.warning("Please provide one clearer image or the original digital PDF.")
    else:
        st.warning((outcome.code or outcome.kind).replace("_", " ").title())
    st.info("Submit the original through the separate fictional Official HR Document Route.")


def history(service: AishaService, repo: Repo) -> None:
    st.markdown(
        '<div class="aisha-chat-head"><p class="aisha-eyebrow">Retained outcomes</p>'
        "<h2>My AISHA history</h2>"
        '<div class="aisha-topic-line">Private conversations and result-only certificate records</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Policy Conversations")
    conversations = repo.list_policy_conversations("emp-alyssa")
    if not conversations:
        st.info("No Policy Conversations yet.")
    for conversation in conversations:
        messages = repo.list_policy_messages(conversation["conversation_id"])
        preview = next((item["text"] for item in messages if item["role"] == "hire"), "Empty conversation")
        st.markdown(
            '<div class="aisha-record"><span class="aisha-outcome">Policy conversation</span>'
            f'<div class="aisha-record-title">{escape(preview[:100])}</div>'
            f'<span class="aisha-muted aisha-small">{escape(conversation["simulated_date"])} · '
            f'{len(messages)} message(s)</span></div>',
            unsafe_allow_html=True,
        )
        if st.button("Delete conversation", key=f"delete-conversation-{conversation['conversation_id']}"):
            repo.delete_policy_conversation(conversation["conversation_id"])
            if st.session_state.get("conversation_id") == conversation["conversation_id"]:
                st.session_state.pop("conversation_id", None)
            st.rerun()

    st.markdown("### Validation Results")
    results = repo.list_validation_results()
    if not results:
        st.info("No retained Validation Results. Files and extracted content never appear here.")
    for result in results:
        tone = "good" if result["status"] == "complete" else "warn"
        st.markdown(
            f'<div class="aisha-record"><span class="aisha-outcome {tone}">'
            f'{escape(result["status"].replace("_", " ").title())}</span>'
            f'<div class="aisha-record-title">{escape(result["policy_id"])} · '
            f'AISHA Handbook v{escape(result["handbook_version"])}</div>'
            f'<span class="aisha-muted aisha-small">Evaluation date '
            f'{escape(result["simulated_evaluation_date"])} · '
            f'{escape(result["share_state"].title())}</span></div>',
            unsafe_allow_html=True,
        )
        action_cols = st.columns(2)
        if result["share_state"] == "private":
            if action_cols[0].button("Share result with HR", key=f"share-{result['validation_id']}", type="primary"):
                service.share_validation_result(result["validation_id"], expected_version=result["resource_version"])
                st.rerun()
        elif action_cols[0].button("Revoke HR access", key=f"revoke-{result['validation_id']}"):
            service.revoke_validation_result(result["validation_id"], expected_version=result["resource_version"])
            st.rerun()
        if action_cols[1].button("Delete result", key=f"delete-result-{result['validation_id']}"):
            service.delete_validation_result(result["validation_id"], expected_version=result["resource_version"])
            st.rerun()


def new_hire_view(service: AishaService, repo: Repo) -> None:
    nav, dialogue, context = st.columns([1.05, 3, 1.15], gap="small")
    with nav:
        with st.container(border=True, key="dialogue_nav"):
            st.markdown(
                '<div class="aisha-profile-block"><p class="aisha-eyebrow">Today</p>'
                "<strong>Onboarding support</strong>"
                '<span class="aisha-muted aisha-small">Active Handbook v1.0</span></div>'
                '<div class="aisha-sr-only">Ask AISHA · Certificate Check · History</div>',
                unsafe_allow_html=True,
            )
            destination = st.radio(
                "Support journeys",
                ["Ask AISHA", "Certificate Check", "History"],
                key="hire_destination",
                label_visibility="collapsed",
            )
    with dialogue:
        with st.container(border=True, key="dialogue_chat"):
            if destination == "Certificate Check":
                certificate_check(service)
            elif destination == "History":
                history(service, repo)
            else:
                ask_aisha(service)
    with context:
        with st.container(border=True, key="dialogue_context"):
            render_context(repo)


def render_hr_cases(repo: Repo) -> None:
    st.markdown("### Consented Escalation Cases")
    cases = repo.list_escalation_cases()
    if not cases:
        st.info("No consented cases. An offer alone never creates an HR-visible record.")
        return
    for case in cases:
        st.markdown(
            '<div class="aisha-record"><span class="aisha-outcome warn">'
            f'{escape(case["status"].title())}</span><div class="aisha-record-title">'
            f'{escape(case["approved_summary"])}</div><span class="aisha-muted aisha-small">'
            f'{escape(case["topic"].replace("_", " ").title())} · {escape(case["route_owner"])}</span></div>',
            unsafe_allow_html=True,
        )
        if case["status"] == "open" and st.button("Mark resolved", key=f"close-case-{case['case_id']}", type="primary"):
            repo.close_escalation_case(case["case_id"], expected_version=case["resource_version"], hr_user="hr-demo")
            st.rerun()


def render_hr_results(repo: Repo) -> None:
    st.markdown("### Shared Validation Results")
    results = repo.list_shared_validation_results()
    if not results:
        st.info("No results have been shared by Alyssa.")
        return
    for result in results:
        st.markdown(
            '<div class="aisha-record"><span class="aisha-outcome warn">Shared result</span>'
            f'<div class="aisha-record-title">{escape(result["status"].replace("_", " ").title())}</div>'
            f'<span class="aisha-muted aisha-small">{escape(result["policy_id"])} · Handbook '
            f'v{escape(result["handbook_version"])} · {escape(result["simulated_evaluation_date"])}</span></div>',
            unsafe_allow_html=True,
        )


def render_hr_attribute_requests(service: AishaService, repo: Repo) -> None:
    st.markdown("### Pending Attribute Change Requests")
    requests = [item for item in repo.list_attribute_change_requests() if item["status"] == "pending"]
    if not requests:
        st.info("No pending requests.")
        return
    for request in requests:
        st.markdown(
            '<div class="aisha-record"><span class="aisha-outcome">Attribute request</span>'
            f'<div class="aisha-record-title">{escape(request["attribute_name"].replace("_", " ").title())}</div>'
            f'<span class="aisha-muted aisha-small">{escape(request["current_value"])} → '
            f'{escape(request["proposed_value"])}</span></div>',
            unsafe_allow_html=True,
        )
        approve, reject = st.columns(2)
        if approve.button("Approve revision", key=f"approve-{request['request_id']}", type="primary"):
            service.resolve_attribute_request(
                request["request_id"], approve=True,
                expected_version=request["resource_version"],
                expected_profile_revision=request["profile_revision"], hr_user="hr-demo",
            )
            st.rerun()
        if reject.button("Reject request", key=f"reject-{request['request_id']}"):
            service.resolve_attribute_request(
                request["request_id"], approve=False,
                expected_version=request["resource_version"],
                expected_profile_revision=request["profile_revision"], hr_user="hr-demo",
            )
            st.rerun()


def hr_view(service: AishaService, repo: Repo) -> None:
    nav, detail = st.columns([1.05, 3.9], gap="small")
    cases = repo.list_escalation_cases()
    shared = repo.list_shared_validation_results()
    requests = [item for item in repo.list_attribute_change_requests() if item["status"] == "pending"]
    with nav:
        with st.container(border=True, key="hr_nav"):
            st.markdown(
                '<div class="aisha-profile-block"><p class="aisha-eyebrow">Dialogue · HR view</p>'
                "<strong>Consented records</strong>"
                '<span class="aisha-muted aisha-small">No transcripts or documents</span></div>',
                unsafe_allow_html=True,
            )
            queue = st.radio(
                "HR support queue",
                [f"Escalations ({len(cases)})", f"Shared results ({len(shared)})", f"Attribute requests ({len(requests)})"],
                key="hr_queue",
                label_visibility="collapsed",
            )
    with detail:
        with st.container(border=True, key="hr_detail"):
            st.markdown(
                '<div class="aisha-detail-head"><p class="aisha-eyebrow">HR support workspace</p>'
                "<h1>Requests Alyssa chose to share</h1>"
                '<div class="aisha-privacy-box">Visible: approved summaries and structured fields. '
                "Hidden: private conversations, certificate contents, and inferred motives.</div></div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="aisha-sr-only">Consented Escalation Cases · Shared Validation Results · '
                "Pending Attribute Change Requests · private chat</div>",
                unsafe_allow_html=True,
            )
            with st.container(key="hr_detail_body"):
                if queue.startswith("Shared"):
                    render_hr_results(repo)
                elif queue.startswith("Attribute"):
                    render_hr_attribute_requests(service, repo)
                else:
                    render_hr_cases(repo)


def demo_controls(repo: Repo) -> None:
    with st.expander("Demo controls", expanded=False):
        st.caption(
            "Full Demo Reset clears product state and rotates the local certificate key. "
            "MLflow and VM backups are separate."
        )
        confirmed = st.checkbox("I understand this clears demo product state", key="reset-confirm")
        if st.button("Full Demo Reset", disabled=not confirmed):
            repo.full_demo_reset()
            st.session_state.clear()
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="AISHA", page_icon="💬", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    repo, service = get_repo(), get_service()
    role = render_topbar()
    if role == "HR User":
        hr_view(service, repo)
    else:
        new_hire_view(service, repo)
    demo_controls(repo)
    st.markdown(f'<p class="aisha-disclaimer">{escape(DISCLAIMER)}</p>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
