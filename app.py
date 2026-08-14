"""AISHA Dialogue workspace for the fictional educational onboarding demo."""

from __future__ import annotations

from datetime import date
from html import escape
import json

import streamlit as st

from stai.handbook import build_handbook
from stai.models import ApplicabilityStatus
from stai.retriever import load_page_records
from stai.retriever import ChromaHandbookIndex
from stai.config import settings
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
.aisha-thread-heading { margin: 14px 0 6px; color: var(--aisha-muted); font-size: 11px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
[class*="st-key-ticket_tree_"] { margin: 2px 0 8px 10px; padding-left: 10px; border-left: 2px solid #c5ceda; }
.aisha-sharing-banner { margin: .75rem 1rem 0; padding: .75rem .85rem; border-left: 4px solid var(--aisha-gold); border-radius: 0 8px 8px 0; background: var(--aisha-soft-gold); color: #604900; font-size: 12px; }
.aisha-case-breadcrumb { color: var(--aisha-muted); font-size: 12px; }
.aisha-case-speaker { margin-bottom: 5px; color: var(--aisha-blue); font-size: 11px; font-weight: 800; text-transform: uppercase; }
.aisha-case-internal { border-style: dashed !important; background: #f4f1ea !important; }
.st-key-conversation_list .stButton > button { min-height: 40px !important; justify-content: flex-start; text-align: left; }
.st-key-conversation_list .stButton > button p { font-size: 12px; }

.stButton > button { border: 1px solid #9ca8b9; border-radius: 9px; background: white; color: var(--aisha-ink); }
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  border-color: var(--aisha-blue) !important; background: var(--aisha-blue) !important; color: white !important;
}
.stButton > button[kind="primary"] p,
button[data-testid="stBaseButton-primary"] p { color: white !important; }
.stButton > button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover { color: white !important; }
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
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    records = load_page_records(artifacts.rag_pages_path, expected_manifest=manifest)
    index = ChromaHandbookIndex(get_repo(), records)
    return AishaService(
        get_repo(),
        records,
        handbook_index=index,
        agent_enabled=settings.agent_enabled,
    )


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
        "escalation_confirmation": ("Case created", "good"),
    }
    label, tone = labels.get(response_type or "", ("AISHA", ""))
    st.markdown(
        f'<span class="aisha-outcome {tone}">{escape(label)}</span>',
        unsafe_allow_html=True,
    )


def evidence_area(response) -> None:
    clarifications = getattr(response, "clarifications", [])
    if not response.citations and not clarifications:
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
        for clarification in clarifications:
            scope = clarification.resolution_scope.value.replace("_", " ").title()
            st.markdown(
                f"- **{clarification.clarification_id}** · reviewed HR clarification · "
                f"{scope} · supplements {', '.join(clarification.related_policy_ids)}"
            )


def action_area(service: AishaService, conversation_id: str, message: dict) -> None:
    """Render persisted action state so controls survive Streamlit reruns."""
    if message.get("role") != "aisha":
        return
    payload = service.repo.get_policy_response_payload(message["id"])
    if not payload:
        return
    if payload["type"] == "escalation_offer":
        st.markdown(
            "**Nothing has been shared yet.** If you consent, HR will receive only "
            f"this summary first: “{payload['proposed_summary']}”\n\n"
            f"Route: {payload['route_owner']} · {payload['route_channel']}\n\n"
            f"**Conversation sharing:** {payload['sharing_notice']}"
        )
        pending = service.repo.get_escalation_offer(payload["offer_id"])
        if not pending:
            st.caption("This offer is no longer pending. See the case confirmation below.")
            return
        if st.button(
            "Consent and create case",
            key=f"consent-{payload['offer_id']}-{message['id']}",
            type="primary",
        ):
            try:
                confirmation = service.consent_escalation_from_conversation(
                    conversation_id,
                    payload["offer_id"],
                    expected_version=payload["version"],
                )
            except (KeyError, ValueError):
                st.warning("This offer changed or was already completed. Refreshing its status…")
            else:
                st.session_state["case_created_notice"] = {
                    "case_id": confirmation.case_id,
                    "route_owner": confirmation.route_owner,
                }
            st.rerun()
    elif payload["type"] == "escalation_confirmation":
        case = service.repo.get_escalation_case(payload["case_id"])
        status = case["status"] if case else "created"
        st.success(
            f"Case reference: {payload['case_id']} · Status: {status} · "
            f"Route: {payload['route_owner']} · {payload['route_channel']}"
        )
        if st.button("Open HR ticket thread", key=f"open-case-{payload['case_id']}-{message['id']}"):
            st.session_state["active_case_id"] = payload["case_id"]
            st.rerun()


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
    linked_cases = service.list_cases(parent_conversation_id=conversation_id)
    active_links = [case for case in linked_cases if case["sharing_active"]]
    if active_links:
        st.markdown(
            '<div class="aisha-sharing-banner"><strong>Shared parent conversation.</strong> '
            f'{len(active_links)} open HR ticket thread(s) receive this chat history and new '
            "messages until they close.</div>",
            unsafe_allow_html=True,
        )
    notice = st.session_state.pop("case_created_notice", None)
    if notice:
        st.success(
            f"Case {notice['case_id']} was created successfully and routed to "
            f"{notice['route_owner']}."
        )
        st.toast("Your support case was created.", icon="✅")
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
            if role == "assistant":
                action_area(service, conversation_id, message)

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
        persisted = service.list_messages(conversation_id)[-1]
        action_area(service, conversation_id, persisted)


def hire_case_thread(service: AishaService, case_id: str) -> None:
    from stai.cases import CaseActor

    service.case_workflow.mark_notifications_read(case_id, CaseActor.hire())
    thread = service.get_case_thread(case_id)
    case = thread["case"]
    resolution = thread.get("resolution")
    parent = case.get("parent_conversation_id")
    parent_title = "Original conversation"
    if parent:
        parent_title = next(
            (
                item["title"]
                for item in service.repo.list_policy_conversations("emp-alyssa")
                if item["conversation_id"] == parent
            ),
            parent_title,
        )
    st.markdown(
        '<div class="aisha-chat-head"><p class="aisha-eyebrow">HR ticket thread</p>'
        f'<h2>{escape(parent_title)} › {escape(case["route_owner"])}</h2>'
        f'<div class="aisha-case-breadcrumb">Case {escape(case_id)} · '
        f'{escape(case["workflow_state"].replace("_", " ").title())}</div></div>',
        unsafe_allow_html=True,
    )
    if case["sharing_active"]:
        st.markdown(
            '<div class="aisha-sharing-banner"><strong>Parent sharing is active.</strong> '
            "Messages from the linked AISHA conversation continue appearing here and are "
            "visible to HR until this ticket closes.</div>",
            unsafe_allow_html=True,
        )
    elif resolution:
        st.success(f"Resolved: {resolution['answer']}")
        st.caption(
            f"{resolution['resolution_type'].replace('_', ' ').title()} · "
            f"{resolution['resolution_scope'].replace('_', ' ').title()} · "
            f"Reuse: {resolution['reuse_status'].replace('_', ' ').title()}"
        )
    for item in thread["messages"]:
        role = "user" if item["actor_role"] == "hire" else "assistant"
        with st.chat_message(role):
            speaker = {
                "hire": "You",
                "aisha": (
                    "AISHA · mirrored parent message"
                    if item.get("source_policy_message_id")
                    else "AISHA · case coordinator"
                ),
                "hr": "HR User · direct conversation",
                "system": "Case workflow",
            }[item["actor_role"]]
            st.markdown(f'<div class="aisha-case-speaker">{escape(speaker)}</div>', unsafe_allow_html=True)
            st.markdown(item["text"])
    if case["status"] == "open":
        if case["workflow_state"] == "waiting_for_hire":
            input_label = "Answer AISHA's question for HR"
        elif thread["interaction_mode"]["mode"] == "direct_consented":
            input_label = "Reply in the consented direct HR conversation"
        else:
            input_label = "Add information to this HR case"
        if thread["interaction_mode"]["mode"] == "direct_offered":
            st.info("HR offered an optional direct conversation. AISHA mediation remains active unless you consent.")
            if st.button("Consent to direct HR conversation", key=f"direct-consent-{case_id}"):
                service.consent_direct_case_conversation(
                    case_id, expected_version=case["resource_version"]
                )
                st.rerun()
        reply = st.chat_input(input_label, key=f"case-reply-{case_id}")
        if reply:
            service.post_case_message(
                case_id,
                reply,
                expected_version=case["resource_version"],
            )
            st.rerun()
    elif resolution:
        follow_up = st.chat_input(
            "Ask AISHA about this HR resolution",
            key=f"case-resolution-follow-up-{case_id}",
        )
        if follow_up:
            service.post_case_message(
                case_id,
                follow_up,
                expected_version=case["resource_version"],
            )
            st.rerun()


def certificate_check(service: AishaService) -> None:
    version = service.records[0].handbook_version if service.records else "1.1"
    st.markdown(
        '<div class="aisha-chat-head"><p class="aisha-eyebrow">Certificate check</p>'
        "<h2>Run a private local completeness check</h2>"
        f'<div class="aisha-topic-line">HRP-004 · AISHA Handbook v{escape(version)} · pp. 78–85</div></div>',
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


def render_hire_navigation(service: AishaService) -> str:
    st.markdown(
        '<div class="aisha-profile-block"><p class="aisha-eyebrow">Today</p>'
        "<strong>Onboarding support</strong>"
        '<span class="aisha-muted aisha-small">Active Handbook v1.1</span></div>'
        '<div class="aisha-sr-only">Ask AISHA · Certificate Check · History</div>',
        unsafe_allow_html=True,
    )
    destination = st.radio(
        "Support journeys",
        ["Ask AISHA", "Certificate Check", "History"],
        key="hire_destination",
        label_visibility="collapsed",
    )
    if destination != "Ask AISHA":
        return destination

    active_conversation = ensure_conversation(service)
    if st.button("＋ New conversation", key="new-policy-conversation", type="primary", width="stretch"):
        created = service.create_conversation("emp-alyssa", DEMO_DATE)
        st.session_state["conversation_id"] = created["id"]
        st.session_state.pop("active_case_id", None)
        st.rerun()
    st.markdown('<div class="aisha-thread-heading">Your conversations</div>', unsafe_allow_html=True)
    with st.container(key="conversation_list"):
        for conversation in service.repo.list_policy_conversations("emp-alyssa"):
            conversation_id = conversation["conversation_id"]
            selected = conversation_id == active_conversation and not st.session_state.get("active_case_id")
            title = conversation["title"] or "New conversation"
            if st.button(
                title[:42],
                key=f"conversation-{conversation_id}",
                type="primary" if selected else "secondary",
                width="stretch",
            ):
                st.session_state["conversation_id"] = conversation_id
                st.session_state.pop("active_case_id", None)
                st.rerun()
            cases = service.list_cases(parent_conversation_id=conversation_id)
            if cases:
                tree_key = f"ticket_tree_{conversation_id.replace('-', '_')}"
                with st.container(key=tree_key):
                    for case in cases:
                        unread = f" · {case['unread_count']} new" if case["unread_count"] else ""
                        label = (
                            f"↳ {case['topic'].replace('_', ' ').title()} ticket · "
                            f"{case['workflow_state'].replace('_', ' ').title()}{unread}"
                        )
                        if st.button(
                            label,
                            key=f"case-thread-{case['case_id']}",
                            type=(
                                "primary"
                                if st.session_state.get("active_case_id") == case["case_id"]
                                else "secondary"
                            ),
                            width="stretch",
                        ):
                            st.session_state["conversation_id"] = conversation_id
                            st.session_state["active_case_id"] = case["case_id"]
                            st.rerun()
    return destination


def render_case_context(service: AishaService, case_id: str) -> None:
    case = service.get_case_thread(case_id)["case"]
    st.markdown('<p class="aisha-eyebrow">Ticket context</p>', unsafe_allow_html=True)
    st.markdown(
        "<div class='aisha-context-list'>"
        f"<div class='aisha-context-item'><span>Case</span><strong>{escape(case_id)}</strong></div>"
        f"<div class='aisha-context-item'><span>Status</span><strong>{escape(case['workflow_state'].replace('_', ' ').title())}</strong></div>"
        f"<div class='aisha-context-item'><span>Route</span><strong>{escape(case['route_owner'])}</strong></div>"
        f"<div class='aisha-context-item'><span>Parent sharing</span><strong>{'Active' if case['sharing_active'] else 'Stopped'}</strong></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="aisha-privacy-box">This ticket receives the consented parent '
        "conversation. Other conversations and certificate contents remain excluded.</div>",
        unsafe_allow_html=True,
    )


def new_hire_view(service: AishaService, repo: Repo) -> None:
    nav, dialogue, context = st.columns([1.05, 3, 1.15], gap="small")
    with nav:
        with st.container(border=True, key="dialogue_nav"):
            destination = render_hire_navigation(service)
    with dialogue:
        with st.container(border=True, key="dialogue_chat"):
            if destination == "Certificate Check":
                certificate_check(service)
            elif destination == "History":
                history(service, repo)
            elif st.session_state.get("active_case_id"):
                hire_case_thread(service, st.session_state["active_case_id"])
            else:
                ask_aisha(service)
    with context:
        with st.container(border=True, key="dialogue_context"):
            if destination == "Ask AISHA" and st.session_state.get("active_case_id"):
                render_case_context(service, st.session_state["active_case_id"])
            else:
                render_context(repo)


def render_hr_cases(service: AishaService) -> None:
    from stai.cases import CaseActor

    st.markdown("### Consented Escalation Cases")
    cases = service.list_cases(hr=True)
    if not cases:
        st.info("No consented cases. An offer alone never creates an HR-visible record.")
        return
    for case in cases:
        st.markdown(
            '<div class="aisha-record"><span class="aisha-outcome warn">'
            f'{escape(case["status"].title())}</span><div class="aisha-record-title">'
            f'{escape(case["approved_summary"])}</div><span class="aisha-muted aisha-small">'
            f'{escape(case["topic"].replace("_", " ").title())} · {escape(case["route_owner"])} · '
            f'{escape(case["workflow_state"].replace("_", " ").title())}</span></div>',
            unsafe_allow_html=True,
        )
        with st.expander(f"Open ticket thread · {case['case_id']}"):
            service.case_workflow.mark_notifications_read(case["case_id"], CaseActor.hr())
            thread = service.get_case_thread(case["case_id"], hr=True)
            for item in thread["messages"]:
                internal = item["visibility"] == "hr_internal"
                speaker = {
                    "hire": "Hire",
                    "aisha": (
                        "AISHA · mirrored parent message"
                        if item.get("source_policy_message_id")
                        else (
                            "AISHA · case resolution memory"
                            if item["text"].startswith("Based on HR's decision for this case:")
                            else "AISHA · case coordinator"
                        )
                    ),
                    "hr": "HR User",
                    "system": "Case workflow",
                }[item["actor_role"]]
                css_class = "aisha-record aisha-case-internal" if internal else "aisha-record"
                label = f"{speaker} · HR internal" if internal else speaker
                st.markdown(
                    f'<div class="{css_class}"><div class="aisha-case-speaker">'
                    f'{escape(label)}</div>{escape(item["text"])}</div>',
                    unsafe_allow_html=True,
                )
            if case["status"] == "open":
                request = st.text_area(
                    "Request one missing detail",
                    key=f"hr-request-{case['case_id']}",
                    placeholder="AISHA will ask this question in the Hire's case thread.",
                )
                if st.button(
                    "Ask through AISHA", key=f"send-hr-request-{case['case_id']}",
                    type="primary", disabled=not request.strip()
                    or case["workflow_state"] == "waiting_for_hire",
                ):
                    service.request_case_information(
                        case["case_id"], request,
                        expected_version=case["resource_version"],
                    )
                    st.rerun()
                internal_note = st.text_area(
                    "HR-only note",
                    key=f"hr-note-{case['case_id']}",
                    placeholder="This note is never visible to the Hire.",
                )
                if st.button(
                    "Save internal note", key=f"save-hr-note-{case['case_id']}",
                    disabled=not internal_note.strip(),
                ):
                    service.post_case_message(
                        case["case_id"], internal_note,
                        expected_version=case["resource_version"], hr=True, internal=True,
                    )
                    st.rerun()
                if thread["interaction_mode"]["mode"] == "mediated":
                    st.caption("Direct HR conversation is exceptional and requires separate Hire consent.")
                    if st.button(
                        "Offer direct human conversation",
                        key=f"offer-direct-{case['case_id']}",
                    ):
                        service.offer_direct_case_conversation(
                            case["case_id"], expected_version=case["resource_version"]
                        )
                        st.rerun()
                resolution = st.text_area(
                    "Resolution summary",
                    key=f"resolution-{case['case_id']}",
                    placeholder="Explain what was resolved or what the Hire should do next.",
                )
                resolution_type = st.selectbox(
                    "Resolution type",
                    [
                        "Policy clarification",
                        "Case exception",
                        "Policy amendment candidate",
                        "Unable to resolve",
                    ],
                    key=f"resolution-type-{case['case_id']}",
                )
                resolution_scope = st.selectbox(
                    "Resolution scope",
                    ["Case only", "Hire", "Organization"],
                    key=f"resolution-scope-{case['case_id']}",
                )
                reusable = False
                if resolution_type == "Policy clarification":
                    reusable = st.checkbox(
                        "Propose this clarification for broader reuse",
                        key=f"resolution-reuse-{case['case_id']}",
                        help=(
                            "A policy owner must review it. Case exceptions and amendment "
                            "candidates never become reusable automatically."
                        ),
                    )
                invalid_reuse = reusable and resolution_scope == "Case only"
                if invalid_reuse:
                    st.caption("Choose Hire or Organization scope before proposing reuse.")
                if st.button(
                    "Resolve case", key=f"resolve-case-{case['case_id']}",
                    disabled=not resolution.strip() or invalid_reuse,
                ):
                    service.resolve_case(
                        case["case_id"], resolution,
                        expected_version=case["resource_version"],
                        resolution_type=resolution_type.lower().replace(" ", "_"),
                        resolution_scope=resolution_scope.lower().replace(" ", "_"),
                        propose_for_reuse=reusable,
                    )
                    st.rerun()
            else:
                resolution = thread.get("resolution")
                if resolution:
                    st.markdown(
                        "**Structured resolution**  \n"
                        f"Type: {resolution['resolution_type'].replace('_', ' ').title()}  \n"
                        f"Scope: {resolution['resolution_scope'].replace('_', ' ').title()}  \n"
                        f"Reuse: {resolution['reuse_status'].replace('_', ' ').title()}"
                    )
                    if resolution["reuse_status"] == "pending_review":
                        approve, reject = st.columns(2)
                        if approve.button(
                            "Approve clarification",
                            key=f"approve-clarification-{case['case_id']}",
                            type="primary",
                        ):
                            service.review_case_clarification(
                                case["case_id"],
                                approve=True,
                                expected_version=resolution["resource_version"],
                            )
                            st.rerun()
                        if reject.button(
                            "Reject reuse",
                            key=f"reject-clarification-{case['case_id']}",
                        ):
                            service.review_case_clarification(
                                case["case_id"],
                                approve=False,
                                expected_version=resolution["resource_version"],
                            )
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
    cases = service.list_cases(hr=True)
    shared = repo.list_shared_validation_results()
    requests = [item for item in repo.list_attribute_change_requests() if item["status"] == "pending"]
    with nav:
        with st.container(border=True, key="hr_nav"):
            st.markdown(
                '<div class="aisha-profile-block"><p class="aisha-eyebrow">Dialogue · HR view</p>'
                "<strong>Consented records</strong>"
                '<span class="aisha-muted aisha-small">Shared ticket threads only</span></div>',
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
                '<div class="aisha-privacy-box">Visible: consented Case Threads and structured fields. '
                "Hidden: unrelated conversations, certificate contents, and inferred motives.</div></div>",
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
                    render_hr_cases(service)


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
