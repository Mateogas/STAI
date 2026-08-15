"""AISHA onboarding-support workspace for the fictional educational demo."""

from __future__ import annotations

from datetime import date
from html import escape
import json
import logging

import streamlit as st

from stai.agent import AgentUnavailableError
from stai.handbook import build_handbook
from stai.retriever import load_page_records
from stai.retriever import ChromaHandbookIndex
from stai.config import settings
from stai.service import AishaService
from stai.state import Repo


logger = logging.getLogger(__name__)


DEMO_DATE = date(2026, 8, 10)
DISCLAIMER = (
    "AISHA is a fictional educational demonstration. It is not affiliated with "
    "or endorsed by BDO Unibank, uses no real BDO employee data, and has no "
    "access to BDO internal systems."
)

# A restrained service-workspace system: calm, legible, and deliberately local.
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
  --aisha-red: #9e3f36;
  --aisha-soft-red: #fff0ed;
  --aisha-shadow: 0 12px 35px rgba(10,36,80,.07);
}
* { box-sizing: border-box; }
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background: var(--aisha-canvas);
  color: var(--aisha-ink);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu { display: none !important; }
[data-testid="stSidebar"] { display: none !important; }
.block-container { max-width: 1280px; padding: .85rem 1.1rem 1.75rem; }
h1, h2, h3, p, li, label, [data-testid="stMarkdownContainer"] { color: var(--aisha-ink); }
h1, h2, h3 { letter-spacing: -.018em; }
button, input, textarea { font: inherit; }
button { cursor: pointer; }
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible,
[role="radio"]:focus-visible, [data-testid="stFileUploaderDropzone"]:focus-visible,
[data-testid="stExpander"] summary:focus-visible {
  outline: 3px solid #58a6ff !important;
  outline-offset: 2px !important;
}
[data-testid="stAppViewContainer"] button,
[data-testid="stFileUploaderDropzone"] { min-height: 44px !important; }

/* Identity and role shell. */
.st-key-aisha_topbar {
  width: 100vw;
  margin: -.85rem calc(50% - 50vw) 0;
  padding: .64rem max(1.25rem, calc((100vw - 1280px) / 2 + 1.1rem));
  background: var(--aisha-navy);
  color: white;
  border-bottom: 3px solid var(--aisha-gold);
  box-shadow: 0 2px 14px rgba(10, 36, 80, .15);
}
.aisha-brand { display: flex; align-items: center; gap: 10px; min-height: 48px; color: white; }
.aisha-logo {
  display: grid; place-items: center; flex: 0 0 38px; width: 38px; height: 38px;
  border-radius: 10px; background: var(--aisha-gold); color: var(--aisha-navy);
  font-size: 18px; font-weight: 850;
}
.aisha-brand strong, .aisha-identity strong { display: block; color: white; }
.aisha-brand small, .aisha-identity span { display: block; color: #c6d0e2; font-size: 11px; }
.aisha-identity { min-height: 42px; padding: 4px 0 4px 16px; border-left: 1px solid rgba(255,255,255,.18); }
.aisha-identity { text-align: right; }
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
.aisha-demo-banner {
  display: flex; align-items: center; gap: 10px; width: fit-content; max-width: 100%;
  margin: .75rem auto 1rem; padding: 7px 12px; border: 1px solid #d3cec0;
  border-radius: 999px; background: rgba(255,253,250,.86); color: #4f5b6d;
  font-size: 12px; line-height: 1.4; box-shadow: 0 3px 12px rgba(10,36,80,.035);
}
.aisha-demo-dot { flex: 0 0 8px; width: 8px; height: 8px; border-radius: 50%; background: var(--aisha-gold); }
.aisha-demo-banner strong { color: var(--aisha-navy); }

/* Shared workspace surfaces. */
.st-key-dialogue_nav, .st-key-dialogue_chat, .st-key-dialogue_context,
.st-key-hr_nav, .st-key-hr_detail {
  height: 100%; min-height: 680px; overflow: hidden;
  border: 1px solid var(--aisha-line) !important;
  border-radius: 16px !important;
  background: var(--aisha-paper) !important;
  box-shadow: var(--aisha-shadow);
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
.aisha-profile-block span { display: block; margin-top: 3px; }

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
.aisha-nav-help { margin: 11px 0 2px; color: var(--aisha-muted); font-size: 11px; line-height: 1.45; }

/* Central dialogue surface. */
.aisha-chat-head { padding: 22px 22px 17px; border-bottom: 1px solid var(--aisha-line); background: #fff; }
.aisha-chat-head h1, .aisha-chat-head h2 { margin: 0; color: var(--aisha-ink); font-size: clamp(20px, 2.3vw, 27px); }
.aisha-topic-line { margin-top: 7px; color: var(--aisha-muted); font-size: 12px; }
.aisha-topic-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 11px; }
.aisha-topic-chip {
  display: inline-flex; align-items: center; min-height: 29px; padding: 5px 9px;
  border: 1px solid #d6dce5; border-radius: 999px; background: #f7f9fc;
  color: #35465e; font-size: 11px; font-weight: 700;
}
.st-key-dialogue_chat > div[data-testid="stVerticalBlock"] { min-height: 678px; }
.st-key-dialogue_chat [data-testid="stChatMessage"] {
  width: calc(100% - 2rem); margin: .85rem 1rem 0; padding: .82rem .95rem;
  border: 1px solid var(--aisha-line); border-radius: 14px; background: white;
  box-shadow: 0 2px 8px rgba(10,36,80,.025);
}
.st-key-dialogue_chat [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
  width: min(80%, calc(100% - 2rem)); margin-left: auto; background: var(--aisha-soft-blue);
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
.aisha-empty, .aisha-empty-state { margin: 1rem; padding: 1.1rem; border-radius: 12px; background: #faf9f5; color: var(--aisha-muted); }
.aisha-empty-state { border: 1px solid #e4e0d6; background: linear-gradient(135deg, #fffdf8 0%, #f7f9fc 100%); }
.aisha-empty-state h3 { margin: 0 0 6px; color: var(--aisha-navy); font-size: 19px; }
.aisha-empty-state p { max-width: 620px; margin: 0; color: #596679; font-size: 13px; line-height: 1.55; }
.aisha-starter-label { margin: 14px 1rem 6px; color: var(--aisha-muted); font-size: 11px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
[class*="st-key-starter_"] .stButton > button {
  height: 100%; min-height: 78px !important; padding: 11px 12px; justify-content: flex-start;
  text-align: left; border-color: #cfd7e4; background: white;
}
[class*="st-key-starter_"] .stButton > button p { color: #233650; font-size: 12px; line-height: 1.35; }
.aisha-outcome {
  display: inline-flex; align-items: center; gap: 6px; margin-bottom: 8px; padding: 5px 9px;
  border: 1px solid #cbd9eb; border-radius: 999px; background: var(--aisha-soft-blue); color: #17477e;
  font-size: 11px; font-weight: 800;
}
.aisha-outcome.warn { border-color: #ecd28f; background: var(--aisha-soft-gold); color: #6d5000; }
.aisha-outcome.good { border-color: #b9d9c2; background: var(--aisha-soft-green); color: var(--aisha-green); }
.aisha-outcome.neutral { border-color: #d4d9e1; background: #eceff3; color: #45546a; }
.aisha-outcome.error { border-color: #e3b7b1; background: var(--aisha-soft-red); color: var(--aisha-red); }
.aisha-outcome-note { margin: 3px 0 9px; color: var(--aisha-muted); font-size: 12px; line-height: 1.45; }
[data-testid="stExpander"] { border-color: var(--aisha-line) !important; background: #faf9f5; }
.aisha-evidence-intro { margin: 0 0 9px; color: var(--aisha-muted); font-size: 12px; }
.aisha-evidence-row { margin: 7px 0; padding: 9px 10px; border-left: 3px solid var(--aisha-blue); background: white; }
.aisha-evidence-row strong, .aisha-evidence-row span { display: block; }
.aisha-evidence-row span { margin-top: 2px; color: var(--aisha-muted); font-size: 11px; }
.aisha-consent-panel {
  margin: 12px 0 8px; padding: 13px 14px; border: 1px solid #e4c675;
  border-radius: 11px; background: #fffaf0;
}
.aisha-consent-panel h4 { margin: 0 0 7px; color: #4e3a00; font-size: 14px; }
.aisha-consent-panel p { margin: 5px 0; color: #5a4b1d; font-size: 12px; line-height: 1.45; }
.aisha-consent-panel strong { color: #40320d; }
.aisha-processing-note { color: var(--aisha-muted); font-size: 12px; }

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
.aisha-boundary-box { margin: 1rem; padding: 14px; border: 1px solid #c5d8ca; border-radius: 11px; background: var(--aisha-soft-green); }
.aisha-boundary-box strong { display: block; margin-bottom: 4px; color: #255837; }
.aisha-boundary-box p { margin: 0; color: #315f40; font-size: 12px; line-height: 1.5; }
.aisha-privacy-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 10px 1rem; }
.aisha-privacy-panel { padding: 12px; border: 1px solid var(--aisha-line); border-radius: 10px; background: #faf9f5; }
.aisha-privacy-panel strong { display: block; margin-bottom: 4px; color: var(--aisha-ink); font-size: 12px; }
.aisha-privacy-panel span { display: block; color: var(--aisha-muted); font-size: 11px; line-height: 1.45; }
.aisha-detail-head { padding: 24px 24px 12px; }
.aisha-detail-head h1 { margin: 4px 0 8px; font-size: clamp(24px, 3vw, 34px); }
.aisha-detail-body, .st-key-hr_detail_body { padding: 0 24px 24px; }
.aisha-fact-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; margin: 12px 0; }
.aisha-fact { min-width: 0; padding: 10px; border-radius: 9px; background: #f2f4f7; overflow-wrap: anywhere; }
.aisha-fact span { display: block; color: var(--aisha-muted); font-size: 11px; }
.aisha-record { margin: .75rem 0; background: #faf9f5; border-color: var(--aisha-line); }
.aisha-record-title { margin: 5px 0; color: var(--aisha-ink); font-weight: 750; }
.aisha-status-note {
  margin: .75rem 1rem; padding: .7rem .85rem; border-left: 4px solid var(--aisha-blue);
  border-radius: 0 8px 8px 0; background: var(--aisha-soft-blue);
}
.aisha-result {
  margin: 1rem; padding: 14px; border: 1px solid #b9d9c2; border-radius: 11px;
  background: var(--aisha-soft-green);
}
.aisha-result.warn { border-color: #ecd28f; background: var(--aisha-soft-gold); }
.aisha-result.error { border-color: #e3b7b1; background: var(--aisha-soft-red); }
.aisha-result strong { display: block; color: var(--aisha-ink); font-size: 16px; }
.aisha-result span { display: block; margin-top: 4px; color: #4e5c6e; font-size: 12px; }
.aisha-section-heading { margin: 1.2rem 0 .4rem; color: var(--aisha-navy); font-size: 16px; }
.aisha-empty-inline { margin: .5rem 0 1rem; padding: 12px; border: 1px dashed #c8cdd5; border-radius: 10px; color: var(--aisha-muted); font-size: 12px; }
.aisha-disclaimer { max-width: 800px; margin: 24px auto 0; color: var(--aisha-muted); font-size: 11px; text-align: center; }
.aisha-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.aisha-thread-heading { margin: 14px 0 6px; color: var(--aisha-muted); font-size: 11px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
[class*="st-key-ticket_tree_"] { margin: 2px 0 8px 10px; padding-left: 10px; border-left: 2px solid #c5ceda; }
.aisha-sharing-banner { margin: .75rem 1rem 0; padding: .75rem .85rem; border-left: 4px solid var(--aisha-gold); border-radius: 0 8px 8px 0; background: var(--aisha-soft-gold); color: #604900; font-size: 12px; }
.aisha-case-breadcrumb { color: var(--aisha-muted); font-size: 12px; }
.aisha-case-speaker { margin-bottom: 5px; color: var(--aisha-blue); font-size: 11px; font-weight: 800; text-transform: uppercase; }
.aisha-case-internal { border-style: dashed !important; background: #f4f1ea !important; }
.st-key-conversation_list .stButton > button { min-height: 44px !important; justify-content: flex-start; text-align: left; }
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
[data-testid="stCheckbox"] label { min-height: 44px; align-items: center; }

@media (max-width: 900px) {
  .st-key-dialogue_context { display: none; }
  .st-key-dialogue_nav, .st-key-dialogue_chat, .st-key-hr_nav, .st-key-hr_detail { min-height: 620px; }
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
  .aisha-nav-help { display: none; }
  .st-key-conversation_list { max-height: 120px; overflow-y: auto; padding-right: 3px; }
  .aisha-privacy-grid { grid-template-columns: 1fr; }
  .aisha-demo-banner { width: 100%; border-radius: 11px; }
  [class*="st-key-starter_"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  [class*="st-key-starter_"] [data-testid="column"] { min-width: 100% !important; }
  [class*="st-key-starter_"] .stButton > button { min-height: 56px !important; }
}
@media (max-width: 480px) {
  .aisha-brand small { display: none; }
  .aisha-brand { min-height: 40px; }
  .aisha-logo { width: 34px; height: 34px; flex-basis: 34px; }
  .aisha-chat-head { padding: 18px 16px 14px; }
  .aisha-chat-head h1, .aisha-chat-head h2 { font-size: 21px; }
  .st-key-dialogue_chat [data-testid="stChatMessage"] { width: calc(100% - 1rem); margin-left: .5rem; margin-right: .5rem; }
  .aisha-empty-state, .aisha-empty { margin: .65rem; }
  .aisha-starter-label { margin-left: .65rem; }
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
    )


def announce(message: str) -> None:
    st.markdown(
        f'<div role="status" aria-live="polite" class="aisha-status-note">{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def outcome_badge(response_type: str | None, payload: dict | None = None) -> None:
    labels = {
        "grounded_answer": ("✓ Handbook answer", "good"),
        "clarification_request": ("? Your detail needed", "warn"),
        "abstention": ("— Unable to confirm", "neutral"),
        "escalation_offer": ("↗ Optional HR support", "warn"),
        "escalation_confirmation": ("✓ Case created", "good"),
    }
    if response_type == "abstention" and payload:
        reason = payload.get("reason")
        if reason in {"insufficient_evidence", "handbook_omission"}:
            labels["abstention"] = ("— Insufficient handbook evidence", "neutral")
        elif reason == "unsupported_topic":
            labels["abstention"] = ("— Outside AISHA's scope", "neutral")
        elif reason == "knowledge_index_outage":
            labels["abstention"] = ("— Handbook temporarily unavailable", "error")
    label, tone = labels.get(response_type or "", ("AISHA", ""))
    st.markdown(
        f'<span class="aisha-outcome {tone}">{escape(label)}</span>',
        unsafe_allow_html=True,
    )
    notes = {
        "grounded_answer": "This answer is supported by the active handbook evidence shown below.",
        "clarification_request": "AISHA paused because one confirmed detail could change which rule applies.",
        "abstention": "AISHA did not make a policy claim without enough eligible evidence.",
        "escalation_offer": "The handbook answers part of this question. Nothing is shared unless you consent below.",
        "escalation_confirmation": "Your reviewed summary is now available to the routed HR support team.",
    }
    if response_type in notes:
        st.markdown(
            f'<div class="aisha-outcome-note">{escape(notes[response_type])}</div>',
            unsafe_allow_html=True,
        )


def evidence_area(response) -> None:
    if isinstance(response, dict):
        citations = response.get("citations", [])
        clarifications = response.get("clarifications", [])
    else:
        citations = response.citations
        clarifications = getattr(response, "clarifications", [])
    if not citations and not clarifications:
        return
    count = len(citations) + len(clarifications)
    with st.expander(f"View evidence · {count} record{'s' if count != 1 else ''}", expanded=False):
        st.markdown(
            '<p class="aisha-evidence-intro">Traceable policy metadata only. '
            "Retrieved handbook passages and ranking data stay hidden.</p>",
            unsafe_allow_html=True,
        )
        for citation in citations:
            value = citation if isinstance(citation, dict) else citation.model_dump(mode="json")
            page = (
                f"Page {value['page_start']}"
                if not value.get("page_end") or value["page_end"] == value["page_start"]
                else f"Pages {value['page_start']}–{value['page_end']}"
            )
            st.markdown(
                '<div class="aisha-evidence-row">'
                f'<strong>Policy {escape(value["policy_id"])}</strong>'
                f'<span>AISHA Handbook v{escape(value["handbook_version"])} · '
                f'Revision 1 · {escape(page)} · active handbook build</span></div>',
                unsafe_allow_html=True,
            )
        for clarification in clarifications:
            value = clarification if isinstance(clarification, dict) else clarification.model_dump(mode="json")
            scope = value["resolution_scope"].replace("_", " ").title()
            st.markdown(
                '<div class="aisha-evidence-row">'
                f'<strong>Reviewed HR clarification {escape(value["clarification_id"])}</strong>'
                f'<span>{escape(scope)} · supplements '
                f'{escape(", ".join(value["related_policy_ids"]))}</span></div>',
                unsafe_allow_html=True,
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
            '<div class="aisha-consent-panel"><h4>Review before sharing</h4>'
            f'<p><strong>Case summary:</strong> {escape(payload["proposed_summary"])}</p>'
            + (
                f'<p><strong>Handbook confirms:</strong> {escape(payload["safe_known_text"])}</p>'
                if payload.get("safe_known_text") else ""
            )
            + (
                f'<p><strong>HR would help answer:</strong> {escape(payload["unresolved_question"])}</p>'
                if payload.get("unresolved_question") else ""
            )
            + f'<p><strong>Route:</strong> {escape(payload["route_owner"])} · '
            f'{escape(payload["route_channel"])}</p>'
            f'<p><strong>What will be shared:</strong> {escape(payload["sharing_notice"])}</p>'
            '<p><strong>Nothing has been shared yet.</strong></p></div>',
            unsafe_allow_html=True,
        )
        pending = service.repo.get_escalation_offer(payload["offer_id"])
        if not pending:
            st.caption("This offer is no longer pending. See the case confirmation below.")
            return
        reviewed = st.checkbox(
            "I reviewed the summary and consent to create this HR-visible case.",
            key=f"review-consent-{payload['offer_id']}-{message['id']}",
        )
        if st.button(
            "Consent and create case",
            key=f"consent-{payload['offer_id']}-{message['id']}",
            type="primary",
            disabled=not reviewed,
        ):
            try:
                confirmation = service.consent_escalation_from_conversation(
                    conversation_id,
                    payload["offer_id"],
                    expected_version=payload["version"],
                )
            except (KeyError, ValueError):
                st.warning("This offer changed or was already completed. Refresh to see its current status.")
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
        if st.button("Open HR case thread", key=f"open-case-{payload['case_id']}-{message['id']}"):
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
                ["Alyssa · Hire", "HR · Support"],
                default="Alyssa · Hire",
                key="role_view",
                label_visibility="collapsed",
                width="stretch",
            )
        with identity:
            if role == "HR · Support":
                name, detail = "HR support", "Shared records only"
            else:
                name, detail = "Alyssa Reyes", "Private Hire workspace"
            st.markdown(
                f'<div class="aisha-identity"><strong>{name}</strong><span>{detail}</span></div>',
                unsafe_allow_html=True,
            )
    return role or "Alyssa · Hire"


def render_demo_banner() -> None:
    st.markdown(
        '<div class="aisha-demo-banner"><span class="aisha-demo-dot"></span>'
        '<span><strong>Fictional BDO educational demo</strong> · No affiliation or '
        "endorsement · No real employee data · No BDO internal-system access · "
        "Support, not surveillance</span></div>",
        unsafe_allow_html=True,
    )


def render_context(repo: Repo) -> None:
    profile = repo.get_hire_profile("emp-alyssa")
    st.markdown('<p class="aisha-eyebrow">Confirmed context</p>', unsafe_allow_html=True)
    st.markdown(
        "<div class='aisha-context-list'>"
        "<div class='aisha-context-item'><span>Role</span>"
        f"<strong>{escape(profile.role_key.replace('_', ' ').title())}</strong></div>"
        "<div class='aisha-context-item'><span>Department</span>"
        f"<strong>{escape(profile.department_key.replace('_', ' ').title())}</strong></div>"
        "<div class='aisha-context-item'><span>Employment</span>"
        f"<strong>{escape(profile.employment_classification.replace('_', ' ').title())}</strong></div>"
        "<div class='aisha-context-item'><span>Work site</span>"
        f"<strong>{escape(profile.work_site.replace('_', ' ').title())}</strong></div>"
        "<div class='aisha-context-item'><span>Simulated date</span>"
        f"<strong>{DEMO_DATE.strftime('%B %d, %Y')}</strong></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="aisha-privacy-box"><strong>Private by default.</strong><br>'
        "Chat never changes these HR-confirmed values and never creates a case automatically.</div>",
        unsafe_allow_html=True,
    )


def suggested_question_buttons() -> str | None:
    st.markdown('<div class="aisha-starter-label">Try a question</div>', unsafe_allow_html=True)
    questions = (
        ("Payroll", "When will I receive my first pay?"),
        ("Resource Access", "How do I request the systems I need?"),
        ("HR Policies", "What should I do when I need sick leave?"),
    )
    selected = None
    with st.container(key="starter_questions"):
        columns = st.columns(3, gap="small")
        for column, (topic, question) in zip(columns, questions, strict=True):
            if column.button(
                f"{topic}\n\n{question}",
                key=f"starter_{topic.lower().replace(' ', '_')}",
                width="stretch",
            ):
                selected = question
    return selected


def ask_aisha(service: AishaService) -> None:
    st.markdown(
        '<div class="aisha-chat-head"><p class="aisha-eyebrow">Alyssa’s private onboarding assistant</p>'
        "<h2>Reach the right onboarding rule, faster</h2>"
        '<div class="aisha-topic-chips"><span class="aisha-topic-chip">Payroll</span>'
        '<span class="aisha-topic-chip">Resource Access</span>'
        '<span class="aisha-topic-chip">HR Policies</span></div>'
        f'<div class="aisha-topic-line">Active Handbook v1.1 · Demo date '
        f'{DEMO_DATE.strftime("%b %d, %Y")} · Local processing</div></div>',
        unsafe_allow_html=True,
    )
    conversation_id = ensure_conversation(service)
    linked_cases = service.list_cases(parent_conversation_id=conversation_id)
    active_links = [case for case in linked_cases if case["sharing_active"]]
    if active_links:
        st.markdown(
            '<div class="aisha-sharing-banner"><strong>Consent-based sharing is active.</strong> '
            f'{len(active_links)} open HR case(s) receive this conversation’s existing and new '
            "messages until each case closes. Other conversations remain private.</div>",
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
    suggested_prompt = None
    if not messages:
        st.markdown(
            '<div class="aisha-empty-state"><h3>Hi Alyssa—what would help you get moving?</h3>'
            "<p>AISHA checks the active synthetic handbook and your HR-confirmed profile. "
            "It answers only when the evidence supports the rule, asks for one deciding "
            "detail when needed, and never contacts HR without your consent.</p></div>",
            unsafe_allow_html=True,
        )
        suggested_prompt = suggested_question_buttons()
    for message in messages:
        role = "user" if message["role"] == "hire" else "assistant"
        with st.chat_message(role):
            if role == "assistant":
                payload = service.repo.get_policy_response_payload(message["id"])
                outcome_badge(message.get("response_type"), payload)
            st.markdown(message["text"])
            if role == "assistant":
                if payload:
                    evidence_area(payload)
                action_area(service, conversation_id, message)

    prompt = suggested_prompt or st.chat_input(
        "Ask about Payroll, Resource Access, or HR Policies",
        key="policy_question",
    )
    if not prompt:
        return
    with st.chat_message("user"):
        st.markdown(prompt)
    try:
        with st.status("Checking the active handbook…", expanded=True) as status:
            st.markdown(
                '<span class="aisha-processing-note">Local CPU processing can take a moment. '
                "Your question stays on this device.</span>",
                unsafe_allow_html=True,
            )
            response = service.send_message(conversation_id, prompt)
            status.update(label="Handbook check complete", state="complete", expanded=False)
    except AgentUnavailableError as exc:
        logger.error("AISHA policy turn failed safely at stage=%s", exc.stage)
        announce("AISHA could not complete the answer safely.")
        st.error(
            "AISHA could not safely complete this answer. No policy answer was saved or "
            "shared. Reload the assistant and try again; if the issue continues, check "
            "the Ollama model and restart the local service."
        )
        if st.button("Reload assistant", key="reload-policy-assistant"):
            st.rerun()
        return
    announce(f"AISHA returned {response.type.replace('_', ' ')}.")
    with st.chat_message("assistant"):
        payload = response.model_dump(mode="json")
        outcome_badge(response.type, payload)
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
        '<div class="aisha-chat-head"><p class="aisha-eyebrow">HR support case</p>'
        f'<h2>{escape(parent_title)} › {escape(case["route_owner"])}</h2>'
        f'<div class="aisha-case-breadcrumb">Case {escape(case_id)} · '
        f'{escape(case["workflow_state"].replace("_", " ").title())}</div></div>',
        unsafe_allow_html=True,
    )
    if case["sharing_active"]:
        st.markdown(
            '<div class="aisha-sharing-banner"><strong>Parent sharing is active.</strong> '
            "Messages from the linked AISHA conversation continue appearing here and are "
            "visible to HR until this case closes. Other conversations remain private.</div>",
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
        '<div class="aisha-chat-head"><p class="aisha-eyebrow">Private local utility</p>'
        "<h2>Check certificate completeness locally</h2>"
        f'<div class="aisha-topic-line">HRP-004 · AISHA Handbook v{escape(version)} · pp. 78–85</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="aisha-boundary-box"><strong>Completeness check only</strong>'
        "<p>This does not verify authenticity, approve leave, assess medical information, "
        "make a diagnosis, or submit a document. Rejected or failed checks create no result.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="aisha-privacy-grid">'
        '<div class="aisha-privacy-panel"><strong>Processed for this check</strong>'
        "<span>The file and extracted text are handled locally and temporarily, then discarded.</span></div>"
        '<div class="aisha-privacy-panel"><strong>Retained after a successful check</strong>'
        "<span>Only the result status, policy/version, evaluation date, and safe reason codes. "
        "It stays private until you choose to share it.</span></div></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Accepted: one PDF, JPG, or PNG · Maximum 10 MB · PDF maximum 3 pages · "
        "Local text extraction/OCR"
    )
    acknowledged = st.checkbox(
        "I understand what is processed, discarded, retained, and not submitted."
    )
    upload = st.file_uploader(
        "Choose a synthetic certificate file",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Use synthetic demo material only. Do not upload a real medical document.",
    )
    if not st.button(
        "Run private local check",
        disabled=upload is None or not acknowledged,
        type="primary",
    ):
        st.info(
            "AISHA does not submit the original. In this fictional workflow, the original "
            "belongs in the separate Official HR Document Route."
        )
        return
    with st.status("Checking the file locally…", expanded=True) as status_area:
        st.markdown(
            '<span class="aisha-processing-note">Reading the file, checking required fields, '
            "and removing temporary content. This can take a moment on CPU.</span>",
            unsafe_allow_html=True,
        )
        profile = service.repo.get_hire_profile("emp-alyssa")
        outcome = service.medical.check(
            upload.getvalue(),
            filename=upload.name,
            evaluation_date=DEMO_DATE,
            applicability=service.certificate_applicability(profile),
            acknowledged=acknowledged,
        )
        status_area.update(label="Local check complete", state="complete", expanded=False)
    announce(f"Certificate Check outcome: {outcome.kind.replace('_', ' ')}.")
    if outcome.kind == "validation_result":
        status = (outcome.status or "complete").replace("_", " ").title()
        tone = "" if status == "Complete" else " warn"
        st.markdown(
            f'<div class="aisha-result{tone}" role="status"><strong>{escape(status)}</strong>'
            '<span>A safe result was retained privately. No file, filename, extracted text, '
            "medical detail, or hidden reasoning appears in history.</span></div>",
            unsafe_allow_html=True,
        )
        with st.expander("What this result means", expanded=True):
            st.markdown(
                "**Complete** means the required demo fields were present and internally "
                "consistent. It does not mean genuine, medically acceptable, approved, or submitted."
            )
        codes = outcome.missing_codes + outcome.inconsistency_codes + outcome.review_codes
        if codes:
            st.markdown("**Result details**")
            for code in codes:
                st.markdown(f"- {code.replace('_', ' ').title()}")
        if outcome.manual_field_summary is not None:
            st.markdown("**Blank Manual Field Summary**")
            st.caption(
                "This ephemeral template is for the separate human route. AISHA does not "
                "collect or retain completed medical fields."
            )
            for field_name in outcome.manual_field_summary:
                st.markdown(f"- {field_name.replace('_', ' ').title()}: —")
    elif outcome.kind == "retry_required":
        st.markdown(
            '<div class="aisha-result warn" role="status"><strong>A clearer file is needed</strong>'
            "<span>AISHA could not read this file confidently. No result was saved. Use one "
            "clearer image or the original digital PDF.</span></div>",
            unsafe_allow_html=True,
        )
    else:
        labels = {
            "file_too_large": "The file is larger than 10 MB.",
            "unsupported_media_type": "The file is not a supported PDF, JPG, or PNG.",
            "extension_content_mismatch": "The file extension does not match its contents.",
            "active_or_embedded_content": "The PDF contains active or embedded content and was rejected.",
            "too_many_pages": "The PDF contains more than three pages.",
            "local_processing_failure": "The local check could not be completed.",
        }
        message = labels.get(
            outcome.code or "",
            (outcome.code or outcome.kind).replace("_", " ").title(),
        )
        st.markdown(
            f'<div class="aisha-result error" role="status"><strong>Check not completed</strong>'
            f'<span>{escape(message)} No result was saved.</span></div>',
            unsafe_allow_html=True,
        )
    st.info(
        "To continue the fictional process, submit the original separately through the "
        "Official HR Document Route."
    )


def history(service: AishaService, repo: Repo) -> None:
    st.markdown(
        '<div class="aisha-chat-head"><p class="aisha-eyebrow">Alyssa’s records</p>'
        "<h2>Private history and shared outcomes</h2>"
        '<div class="aisha-topic-line">Conversations stay private unless linked to a case you consented to</div></div>',
        unsafe_allow_html=True,
    )
    notice = st.session_state.pop("history_notice", None)
    if notice:
        st.success(notice)
        announce(notice)
    st.markdown(
        '<div class="aisha-boundary-box"><strong>You control what leaves this view</strong>'
        "<p>HR cannot browse your Policy Conversations. HR sees only a consented Case Thread "
        "or the safe certificate result metadata you explicitly share.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown('<h3 class="aisha-section-heading">Policy Conversations</h3>', unsafe_allow_html=True)
    conversations = repo.list_policy_conversations("emp-alyssa")
    if not conversations:
        st.markdown(
            '<div class="aisha-empty-inline">No Policy Conversations yet. Start in Ask AISHA.</div>',
            unsafe_allow_html=True,
        )
    for conversation in conversations:
        messages = repo.list_policy_messages(conversation["conversation_id"])
        preview = next((item["text"] for item in messages if item["role"] == "hire"), "Empty conversation")
        cases = service.list_cases(parent_conversation_id=conversation["conversation_id"])
        st.markdown(
            '<div class="aisha-record"><span class="aisha-outcome">Policy conversation</span>'
            f'<div class="aisha-record-title">{escape(preview[:100])}</div>'
            f'<span class="aisha-muted aisha-small">{escape(conversation["simulated_date"])} · '
            f'{len(messages)} message(s) · {len(cases)} linked case(s)</span></div>',
            unsafe_allow_html=True,
        )
        open_col, delete_col = st.columns(2)
        if open_col.button(
            "Open conversation",
            key=f"open-conversation-{conversation['conversation_id']}",
            width="stretch",
        ):
            st.session_state["conversation_id"] = conversation["conversation_id"]
            st.session_state.pop("active_case_id", None)
            st.session_state["pending_hire_destination"] = "Ask AISHA"
            st.rerun()
        if delete_col.button(
            "Delete conversation",
            key=f"delete-conversation-{conversation['conversation_id']}",
            width="stretch",
        ):
            repo.delete_policy_conversation(conversation["conversation_id"])
            if st.session_state.get("conversation_id") == conversation["conversation_id"]:
                st.session_state.pop("conversation_id", None)
            st.session_state["history_notice"] = "Conversation deleted from this local demo."
            st.rerun()

    st.markdown('<h3 class="aisha-section-heading">HR Support Cases</h3>', unsafe_allow_html=True)
    cases = service.list_cases()
    if not cases:
        st.markdown(
            '<div class="aisha-empty-inline">No HR cases. An offer never becomes a case without your consent.</div>',
            unsafe_allow_html=True,
        )
    for case in cases:
        tone = "good" if case["status"] == "closed" else "warn"
        st.markdown(
            f'<div class="aisha-record"><span class="aisha-outcome {tone}">'
            f'{escape(case["workflow_state"].replace("_", " ").title())}</span>'
            f'<div class="aisha-record-title">{escape(case["approved_summary"])}</div>'
            f'<span class="aisha-muted aisha-small">Case {escape(case["case_id"])} · '
            f'{escape(case["route_owner"])}</span></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Open case thread",
            key=f"history-open-case-{case['case_id']}",
            width="stretch",
        ):
            st.session_state["conversation_id"] = case["parent_conversation_id"]
            st.session_state["active_case_id"] = case["case_id"]
            st.session_state["pending_hire_destination"] = "Ask AISHA"
            st.rerun()

    st.markdown('<h3 class="aisha-section-heading">Certificate Check Results</h3>', unsafe_allow_html=True)
    results = repo.list_validation_results()
    if not results:
        st.markdown(
            '<div class="aisha-empty-inline">No retained results. Files and extracted content never appear here.</div>',
            unsafe_allow_html=True,
        )
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
        st.caption(
            "If shared, HR receives only this status, policy ID, handbook version, and "
            "evaluation date—not the file or its contents."
        )
        action_cols = st.columns(2)
        if result["share_state"] == "private":
            if action_cols[0].button("Share result with HR", key=f"share-{result['validation_id']}", type="primary"):
                service.share_validation_result(result["validation_id"], expected_version=result["resource_version"])
                st.session_state["history_notice"] = "Safe result metadata shared with HR."
                st.rerun()
        elif action_cols[0].button("Revoke HR access", key=f"revoke-{result['validation_id']}"):
            service.revoke_validation_result(result["validation_id"], expected_version=result["resource_version"])
            st.session_state["history_notice"] = "HR access to this result was revoked."
            st.rerun()
        if action_cols[1].button("Delete result", key=f"delete-result-{result['validation_id']}"):
            service.delete_validation_result(result["validation_id"], expected_version=result["resource_version"])
            st.session_state["history_notice"] = "Safe result deleted from this local demo."
            st.rerun()


def render_hire_navigation(service: AishaService) -> str:
    pending_destination = st.session_state.pop("pending_hire_destination", None)
    if pending_destination:
        st.session_state["hire_destination"] = pending_destination
    st.markdown(
        '<div class="aisha-profile-block"><p class="aisha-eyebrow">Alyssa’s workspace</p>'
        "<strong>Onboarding support</strong>"
        '<span class="aisha-muted aisha-small">Active Handbook v1.1 · local</span></div>'
        '<div class="aisha-sr-only">Ask AISHA · Certificate Check · History</div>',
        unsafe_allow_html=True,
    )
    destination = st.radio(
        "Support journeys",
        ["Ask AISHA", "Certificate Check", "History"],
        key="hire_destination",
        label_visibility="collapsed",
    )
    st.markdown(
        '<p class="aisha-nav-help">Ask a policy question, run a separate private certificate '
        "check, or review what is retained and shared.</p>",
        unsafe_allow_html=True,
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
                            f"↳ {case['topic'].replace('_', ' ').title()} case · "
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
    st.markdown('<p class="aisha-eyebrow">Case context</p>', unsafe_allow_html=True)
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
        '<div class="aisha-privacy-box">This case receives the consented parent '
        "conversation. Other conversations and certificate contents remain excluded.</div>",
        unsafe_allow_html=True,
    )


def new_hire_view(service: AishaService, repo: Repo) -> None:
    nav, dialogue, context = st.columns([1.1, 3.4, 1.15], gap="small")
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
    st.caption(
        "Only cases Alyssa explicitly created after reviewing the sharing notice appear here."
    )
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
        with st.expander(f"Open case thread · {case['case_id']}"):
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
                '<div class="aisha-profile-block"><p class="aisha-eyebrow">Separate HR support view</p>'
                "<strong>Shared records only</strong>"
                '<span class="aisha-muted aisha-small">No private chat browser</span></div>',
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
                "<h1>What Alyssa chose to share</h1>"
                '<div class="aisha-privacy-box"><strong>Support signals—not surveillance.</strong><br>'
                "Visible: consented Case Threads and structured records. Hidden: unrelated private "
                "conversations, certificate contents, extracted medical information, and inferred motives.</div></div>",
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
        st.caption(f"The interface uses a fixed simulated date: {DEMO_DATE.strftime('%B %d, %Y')}.")
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
    st.set_page_config(page_title="AISHA · Onboarding Support", page_icon="A", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    repo, service = get_repo(), get_service()
    role = render_topbar()
    render_demo_banner()
    if role == "HR · Support":
        hr_view(service, repo)
    else:
        new_hire_view(service, repo)
    demo_controls(repo)
    st.markdown(f'<p class="aisha-disclaimer">{escape(DISCLAIMER)}</p>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
