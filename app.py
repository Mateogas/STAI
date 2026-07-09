"""STAI - Streamlit entry point for the AISHA educational demo.

The UI is a Streamlit cockpit for the fictionalized AISHA/BDO capstone:
- New hires see Day 30 readiness, real ramp tasks, helpers, and chat.
- People Experience sees support signals and explicit help requests, not raw
  private chat transcripts.

Run: uv run streamlit run app.py
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from stai import pulse
from stai.agent import build_agent, stream_agent_text
from stai.config import settings
from stai.guardrails import REFUSALS, apply_output_guardrails, classify_input
from stai.models import (
    PHASE_LABELS,
    PHASE_ORDER,
    ChecklistItem,
    Employee,
    Escalation,
    Person,
    PulseRecord,
)
from stai.observability import TurnRecord, estimate_tokens, log_turn
from stai.state import Repo
from stai.tools import load_org, match_people

st.set_page_config(
    page_title="AISHA - BDO educational demo",
    page_icon=":material/support_agent:",
    layout="wide",
)

HR_ADMIN = "hr_admin"
DISCLAIMER = (
    "AISHA is an educational capstone prototype. It is not affiliated with, "
    "endorsed by, or representative of BDO Unibank. All records, contacts, "
    "documents, metrics, and interactions in this demo are fictionalized."
)
SHORT_DISCLAIMER = (
    "Fictionalized BDO educational capstone - not affiliated with or endorsed "
    "by BDO Unibank."
)

ACCESS_TERMS = {
    "access",
    "badge",
    "email",
    "laptop",
    "login",
    "mfa",
    "portal",
    "sandbox",
    "workstation",
}
BLOCKER_TERMS = ACCESS_TERMS | {"blocker", "blocked", "issue", "reset"}
SUPPORT_TASK_TERMS = BLOCKER_TERMS | {
    "aml",
    "buddy",
    "check-in",
    "checkin",
    "compliance",
    "confidentiality",
    "manager",
    "privacy",
}


@st.cache_resource
def get_repo() -> Repo:
    repo = Repo()
    repo.seed_if_empty()
    return repo


@st.cache_data(ttl=30)
def kb_ready() -> bool:
    try:
        from stai.retriever import collection_count

        return collection_count() > 0
    except Exception:
        return False


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --aisha-navy: #0a2450;
            --aisha-blue: #0b4da2;
            --aisha-gold: #c9962c;
            --aisha-bg: #f1eee7;
            --aisha-card: #fffdf9;
            --aisha-line: #e7e4dc;
            --aisha-muted: #6b6a63;
        }
        .stApp {
            background: var(--aisha-bg);
            color: var(--aisha-navy);
        }
        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background: var(--aisha-bg);
        }
        [data-testid="stHeader"] {
            display: none;
            height: 0;
        }
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
        }
        .block-container {
            padding-top: 0;
            padding-bottom: 1.2rem;
            padding-left: 1.75rem;
            padding-right: 1.75rem;
            max-width: 1180px;
        }
        h1, h2, h3 {
            color: var(--aisha-navy);
            letter-spacing: 0;
        }
        .stMarkdown,
        .stCaptionContainer,
        [data-testid="stMarkdownContainer"],
        [data-testid="stCaptionContainer"] {
            color: var(--aisha-navy);
        }
        [data-testid="stSidebar"] {
            display: none;
        }
        .aisha-topbar {
            background: var(--aisha-navy);
            color: #ffffff;
            width: 100vw;
            margin-top: -16px;
            margin-left: calc(50% - 50vw);
            margin-right: calc(50% - 50vw);
            margin-bottom: 0;
        }
        .aisha-topbar-inner {
            max-width: 1180px;
            margin: 0 auto;
            padding: 13px 28px;
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .aisha-brand {
            display: flex;
            align-items: center;
            gap: 11px;
            min-width: 210px;
        }
        .aisha-logo {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            background: var(--aisha-gold);
            color: var(--aisha-navy);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 18px;
        }
        .aisha-brand-title {
            font-size: 19px;
            font-weight: 750;
            line-height: 1.05;
        }
        .aisha-brand-subtitle {
            font-size: 11px;
            color: #9fb0cf;
        }
        .aisha-topbar-note {
            margin-left: auto;
            max-width: 330px;
            color: #9fb0cf;
            font-size: 11px;
            line-height: 1.45;
            text-align: right;
        }
        .aisha-persona-pill {
            display: flex;
            align-items: center;
            gap: 9px;
            padding: 6px 12px 6px 6px;
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 999px;
            min-width: 220px;
        }
        .aisha-avatar {
            width: 30px;
            height: 30px;
            border-radius: 999px;
            background: #123166;
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 750;
            flex-shrink: 0;
        }
        .aisha-persona-name {
            font-size: 12.5px;
            font-weight: 700;
            line-height: 1.15;
        }
        .aisha-persona-role {
            color: #9fb0cf;
            font-size: 10.5px;
            line-height: 1.2;
        }
        .aisha-demo-strip {
            background: #081c3c;
            border-top: 1px solid rgba(255,255,255,0.06);
            color: #9fb0cf;
            width: 100vw;
            margin-left: calc(50% - 50vw);
            margin-right: calc(50% - 50vw);
            margin-bottom: 0;
        }
        .aisha-demo-strip-inner {
            max-width: 1180px;
            margin: 0 auto;
            padding: 9px 28px;
        }
        .aisha-demo-label {
            color: #6e7ea0;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.1px;
            text-transform: uppercase;
            margin-bottom: 7px;
        }
        .aisha-page-kicker {
            color: var(--aisha-muted);
            font-size: 13px;
            margin: -12px 0 14px;
        }
        .aisha-hero {
            background: var(--aisha-navy);
            color: #ffffff;
            border-radius: 16px;
            padding: 28px 28px;
            margin-bottom: 0;
        }
        .aisha-eyebrow {
            color: #f0c978;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.6px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .aisha-hero h1 {
            color: #ffffff;
            font-size: 25px;
            line-height: 1.25;
            margin: 0 0 16px;
            max-width: 640px;
        }
        .aisha-hero-meta {
            color: #c6d1e6;
            font-size: 13px;
            margin-bottom: 9px;
        }
        .aisha-progress-track {
            width: 100%;
            height: 9px;
            background: rgba(255,255,255,0.13);
            border-radius: 999px;
            overflow: hidden;
        }
        .aisha-progress-fill {
            height: 100%;
            background: var(--aisha-gold);
            border-radius: 999px;
        }
        .aisha-stage-rail {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 8px;
            margin-top: 16px;
        }
        .aisha-stage-segment {
            min-width: 0;
            text-align: center;
        }
        .aisha-stage-bar {
            height: 5px;
            border-radius: 999px;
            margin-bottom: 6px;
            background: rgba(255,255,255,0.14);
        }
        .aisha-stage-bar.done,
        .aisha-stage-bar.current {
            background: var(--aisha-gold);
        }
        .aisha-stage-label {
            color: #7f90b2;
            font-size: 10px;
            line-height: 1.2;
        }
        .aisha-stage-label.done,
        .aisha-stage-label.current {
            color: #eef3fb;
        }
        .aisha-stage-label.current {
            font-weight: 800;
        }
        .aisha-section-note {
            color: var(--aisha-muted);
            font-size: 12px;
            margin-top: -6px;
            margin-bottom: 12px;
        }
        .aisha-footer {
            color: #8f8b80;
            font-size: 10.5px;
            line-height: 1.5;
            display: block;
            width: min(760px, 100%);
            margin: 18px auto 0 !important;
            text-align: center;
        }
        .aisha-chipline {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 8px;
        }
        .aisha-mini-label {
            color: #8a887f;
            font-size: 11px;
            font-weight: 650;
            letter-spacing: 0.6px;
            text-transform: uppercase;
        }
        div[data-testid="stHorizontalBlock"]:has(.st-key-persona_picker) {
            background: #081c3c;
            width: 100vw !important;
            min-width: 100vw;
            max-width: 100vw;
            margin-left: calc(50% - 50vw);
            margin-right: calc(50% - 50vw);
            margin-bottom: 26px;
            padding: 0 max(28px, calc((100vw - 1180px) / 2 + 28px)) 10px;
        }
        div[data-testid="stHorizontalBlock"]:has(.st-key-persona_picker) label,
        div[data-testid="stHorizontalBlock"]:has(.st-key-persona_picker) p,
        div[data-testid="stHorizontalBlock"]:has(.st-key-persona_picker) [data-testid="stMarkdownContainer"] {
            color: #9fb0cf;
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .aisha-card-heading),
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .aisha-chat-heading) {
            background: var(--aisha-card);
            border: 1px solid var(--aisha-line);
            border-radius: 16px;
            box-shadow: none;
            padding: 16px;
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .aisha-chat-heading) {
            max-height: calc(100vh - 190px);
            overflow-y: auto;
            position: sticky;
            top: 18px;
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .aisha-chat-heading) [data-testid="stForm"] {
            background: #ffffff;
            bottom: -16px;
            margin: 0 -1rem -1rem;
            padding: 12px 14px 14px;
            position: sticky;
            z-index: 5;
        }
        .aisha-card-heading {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 4px;
        }
        .aisha-card-heading h2 {
            font-size: 20px;
            line-height: 1.15;
            margin: 0;
        }
        .aisha-task-row {
            align-items: center;
            border-bottom: 1px solid #eeeae2;
            padding: 10px 0;
        }
        .aisha-task-row:last-child {
            border-bottom: 0;
        }
        .aisha-task-id {
            color: #0a2450;
            font-weight: 800;
        }
        .aisha-task-title {
            color: #0a2450;
            font-weight: 750;
            line-height: 1.35;
        }
        .aisha-chat-heading {
            background: var(--aisha-navy);
            color: #ffffff;
            border-radius: 14px 14px 0 0;
            margin: -1rem -1rem 0.25rem;
            padding: 15px 18px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .aisha-chat-heading .aisha-logo {
            width: 30px;
            height: 30px;
            border-radius: 9px;
            font-size: 15px;
        }
        .aisha-chat-title {
            color: #ffffff;
            font-size: 16px;
            font-weight: 800;
            line-height: 1.1;
        }
        .aisha-chat-subtitle {
            color: #9fb0cf;
            font-size: 11px;
            margin-top: 2px;
        }
        .aisha-chat-body-note {
            color: var(--aisha-muted);
            font-size: 12px;
            margin-bottom: 6px;
        }
        .aisha-composer {
            border-top: 1px solid var(--aisha-line);
            margin: 0 -1rem -1rem;
            padding: 12px 14px 14px;
            background: #ffffff;
            border-radius: 0 0 14px 14px;
        }
        .aisha-people-grid {
            display: grid;
            gap: 10px;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-top: 8px;
        }
        .aisha-person-chip {
            align-items: center;
            background: #fbfaf7;
            border: 1px solid #e7e4dc;
            border-radius: 13px;
            display: flex;
            gap: 10px;
            min-width: 0;
            padding: 10px 11px;
        }
        .aisha-person-avatar {
            align-items: center;
            background: var(--aisha-navy);
            border-radius: 999px;
            color: #ffffff;
            display: flex;
            flex: 0 0 34px;
            font-size: 11px;
            font-weight: 800;
            height: 34px;
            justify-content: center;
            width: 34px;
        }
        .aisha-person-name {
            color: var(--aisha-navy);
            font-size: 13px;
            font-weight: 800;
            line-height: 1.2;
        }
        .aisha-person-role {
            color: var(--aisha-muted);
            font-size: 11px;
            line-height: 1.3;
            margin-top: 2px;
        }
        .aisha-metric-grid {
            display: grid;
            gap: 14px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin: 18px 0 22px;
        }
        .aisha-metric-card {
            background: #fffdf9;
            border: 1px solid #e7e4dc;
            border-radius: 14px;
            padding: 16px 18px;
        }
        .aisha-metric-card.warn {
            background: #fdf7e9;
            border-color: #f0dfb4;
        }
        .aisha-metric-value {
            color: var(--aisha-navy);
            font-size: 29px;
            font-weight: 850;
            line-height: 1;
        }
        .aisha-metric-card.warn .aisha-metric-value {
            color: #b7791f;
        }
        .aisha-metric-label {
            color: var(--aisha-muted);
            font-size: 11.5px;
            margin-top: 6px;
        }
        .aisha-support-card {
            background: #fffdf9;
            border: 1px solid #e7e4dc;
            border-radius: 16px;
            margin-bottom: 13px;
            padding: 18px 18px 16px;
        }
        .aisha-support-card-head {
            align-items: start;
            display: flex;
            gap: 12px;
            justify-content: space-between;
            margin-bottom: 14px;
        }
        .aisha-status-pill {
            background: #fbefcf;
            border-radius: 999px;
            color: #8a6414;
            flex-shrink: 0;
            font-size: 10.5px;
            font-weight: 800;
            padding: 5px 10px;
        }
        .aisha-signal-list {
            color: #4a4a44;
            font-size: 12.5px;
            line-height: 1.45;
            margin: 0 0 12px 18px;
            padding: 0;
        }
        .aisha-action-note {
            background: #fdf7e9;
            border: 1px solid #f0dfb4;
            border-radius: 11px;
            color: #0a2450;
            font-size: 12.5px;
            line-height: 1.45;
            padding: 11px 13px;
        }
        .aisha-privacy-note {
            color: #8a887f;
            font-size: 10.8px;
            line-height: 1.4;
            margin-top: 10px;
        }
        [data-testid="stExpander"] {
            background: rgba(255, 253, 249, 0.62);
            border: 1px solid var(--aisha-line);
            border-radius: 10px;
        }
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary p {
            color: var(--aisha-navy);
        }
        [data-testid="stChatMessage"] {
            background: var(--aisha-card);
            border: 1px solid var(--aisha-line);
            border-radius: 14px;
            color: var(--aisha-navy);
            margin-bottom: 10px;
            padding: 0.75rem 0.85rem;
        }
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stChatMessage"] [data-testid="stChatMessageContent"],
        [data-testid="stChatMessage"] p,
        [data-testid="stChatMessage"] li {
            color: var(--aisha-navy);
        }
        [data-testid="stChatMessage"] a {
            color: var(--aisha-blue);
        }
        [data-testid="stChatInput"],
        [data-testid="stChatInput"] textarea,
        [data-testid="stChatInput"] [contenteditable="true"] {
            background: var(--aisha-card);
            color: var(--aisha-navy);
        }
        [data-testid="stChatInput"] textarea::placeholder {
            color: var(--aisha-muted);
            opacity: 1;
        }
        .stTextInput input {
            background: #f5f3ee;
            border: 1px solid #e2ded4;
            color: var(--aisha-navy);
            border-radius: 10px;
        }
        .stTextInput input::placeholder {
            color: var(--aisha-muted);
            opacity: 1;
        }
        .stButton > button,
        button[data-testid="stBaseButton-primary"],
        button[data-testid="stBaseButton-secondary"] {
            background: var(--aisha-card) !important;
            border: 1px solid #d8d2c6 !important;
            color: var(--aisha-navy) !important;
            box-shadow: none !important;
        }
        .stButton > button:hover,
        button[data-testid="stBaseButton-primary"]:hover,
        button[data-testid="stBaseButton-secondary"]:hover {
            background: #fff8e8 !important;
            border-color: var(--aisha-gold) !important;
            color: var(--aisha-navy) !important;
        }
        @media (max-width: 900px) {
            .aisha-topbar-inner {
                align-items: flex-start;
                flex-direction: column;
            }
            .aisha-topbar-note {
                margin-left: 0;
                text-align: left;
            }
            .aisha-persona-pill {
                width: 100%;
            }
            .aisha-demo-strip-inner {
                padding-left: 18px;
                padding-right: 18px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initials(name: str) -> str:
    parts = [p for p in name.replace("/", " ").split() if p]
    return "".join(p[0].upper() for p in parts[:2]) or "A"


def compact_role(role: str, limit: int = 52) -> str:
    role = role.strip()
    return role if len(role) <= limit else role[: limit - 3].rstrip() + "..."


def short_text(text: str, limit: int = 76) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def text_has_any(text: str, terms: set[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def persona_label(pid: str, employees: list[Employee]) -> str:
    if pid == HR_ADMIN:
        return "People Experience - Support Console"
    emp = next(e for e in employees if e.id == pid)
    return f"{emp.name} - {emp.role}"


def default_sim_date(employees: list[Employee]) -> date:
    if not employees:
        return date(2026, 7, 9)
    return max(e.start_date for e in employees) + timedelta(days=14)


def current_phase_key(employee: Employee, sim_date: date) -> str:
    days = (sim_date - employee.start_date).days
    if days < 0:
        return "pre_start"
    if days == 0:
        return "day_1"
    if days <= 7:
        return "week_1"
    if days < 30:
        return "week_2"
    return "day_30"


def progress_ratio(done: int, total: int) -> float:
    return done / total if total else 0.0


def progress_percent(done: int, total: int) -> int:
    return round(100 * progress_ratio(done, total)) if total else 0


def likely_helper(query: str, people: list[Person]) -> Person | None:
    matches = match_people(query, people, top_n=1)
    if matches:
        return matches[0]
    return next((p for p in people if p.team == "People Experience"), None)


def person_by_name(name: str, people: list[Person]) -> Person | None:
    wanted = name.strip().lower()
    return next((p for p in people if p.name.lower() == wanted), None)


def dedupe_people(people: list[Person]) -> list[Person]:
    seen: set[str] = set()
    out: list[Person] = []
    for person in people:
        if person.id in seen:
            continue
        seen.add(person.id)
        out.append(person)
    return out


def helper_list(employee: Employee, open_items: list[ChecklistItem]) -> list[Person]:
    people = load_org()
    helpers: list[Person] = []
    for name in [employee.manager, employee.buddy]:
        person = person_by_name(name, people)
        if person:
            helpers.append(person)
    for item in open_items[:5]:
        person = likely_helper(item.title, people)
        if person:
            helpers.append(person)
    px = next((p for p in people if p.role == "People Experience Lead"), None)
    if px:
        helpers.append(px)
    return dedupe_people(helpers)[:6]


def is_new_hire_blocker(item: ChecklistItem) -> bool:
    return not item.done and text_has_any(item.title, BLOCKER_TERMS)


def is_support_signal_task(item: ChecklistItem) -> bool:
    return not item.done and text_has_any(item.title, SUPPORT_TASK_TERMS)


def task_signal_label(item: ChecklistItem) -> str:
    title = item.title.lower()
    if "sandbox" in title:
        return "Sandbox access task open"
    if "aml" in title:
        return "AML task open"
    if "privacy" in title or "confidentiality" in title:
        return "Privacy task open"
    if "mfa" in title or "login" in title or "email" in title or "access" in title:
        return "Access task open"
    if "buddy" in title:
        return "Buddy task open"
    if "manager" in title or "check-in" in title or "checkin" in title:
        return "Manager check-in task open"
    if "compliance" in title:
        return "Compliance task open"
    return f"Task open: {short_text(item.title, 44)}"


def expected_progress_floor(employee: Employee, sim_date: date) -> float:
    phase = current_phase_key(employee, sim_date)
    return {
        "pre_start": 0.0,
        "day_1": 0.10,
        "week_1": 0.25,
        "week_2": 0.45,
        "day_30": 0.80,
    }[phase]


def make_blockers(
    employee: Employee,
    open_items: list[ChecklistItem],
    open_escalations: list[Escalation],
) -> list[dict]:
    people = load_org()
    blockers: list[dict] = []
    for item in open_items:
        if not is_new_hire_blocker(item):
            continue
        helper = likely_helper(item.title, people)
        blockers.append(
            {
                "kind": "task",
                "item": item,
                "title": item.title,
                "state": "Task still open",
                "description": "Not yet marked done on your ramp plan.",
                "helper": helper,
            }
        )
    px = next((p for p in people if p.role == "People Experience Lead"), None)
    for esc in open_escalations:
        if esc.employee_id != employee.id:
            continue
        blockers.append(
            {
                "kind": "escalation",
                "escalation": esc,
                "title": esc.question,
                "state": "Open help request",
                "description": esc.details or "People Experience has this request open.",
                "helper": px,
            }
        )
    return blockers[:3]


def support_action(signals: list[str]) -> str:
    joined = " ".join(signals).lower()
    if "help request" in joined:
        return "Review the explicit help request and respond through People Experience."
    if "access" in joined or "sandbox" in joined:
        return "Offer help unblocking access with the right support owner."
    if "aml" in joined or "privacy" in joined or "compliance" in joined:
        return "Clarify the compliance learning step and who can answer questions."
    if "pulse" in joined:
        return "Offer a supportive check-in focused on clarity and tools."
    return "Clarify the next one or two ramp tasks and the expected support path."


def build_support_profiles(
    employees: list[Employee],
    repo: Repo,
    sim_date: date,
    open_escalations: list[Escalation],
) -> list[dict]:
    profiles: list[dict] = []
    for employee in employees:
        items = repo.list_plan_items(employee.id)
        open_items = [item for item in items if not item.done]
        done, total = repo.progress(employee.id)
        history = repo.pulse_history(employee.id)
        scores = [record.sentiment for record in history]
        latest = history[-1] if history else None
        employee_escalations = [
            esc for esc in open_escalations if esc.employee_id == employee.id
        ]

        signals: list[str] = []
        if employee_escalations:
            signals.append(f"Open help request #{employee_escalations[0].id}")
        if pulse.risk_flag(scores):
            trend = pulse.trend(scores)
            trend_text = f", {trend}" if trend != "-" else ""
            signals.append(f"Pulse: {scores[-1]}/5{trend_text}")
        if latest and latest.concerns:
            signals.append("Tags: " + ", ".join(latest.concerns[:3]))
        for item in open_items:
            if is_support_signal_task(item):
                label = task_signal_label(item)
                if label not in signals:
                    signals.append(label)
            if len([s for s in signals if "task open" in s.lower()]) >= 3:
                break
        if (
            total
            and progress_ratio(done, total) < expected_progress_floor(employee, sim_date)
        ):
            signals.append(f"Progress: {done}/{total} tasks done")

        profiles.append(
            {
                "employee": employee,
                "signals": signals[:6],
                "needs_support": bool(signals),
                "done": done,
                "total": total,
                "stage": PHASE_LABELS[current_phase_key(employee, sim_date)],
                "latest_pulse": latest,
                "pulse_trend": pulse.trend(scores),
                "action": support_action(signals) if signals else "",
            }
        )
    return profiles


def render_top_bar(persona_id: str, employees: list[Employee]) -> None:
    if persona_id == HR_ADMIN:
        name = "People Experience"
        role = "Support Console"
        avatar = "PX"
    else:
        employee = next(e for e in employees if e.id == persona_id)
        name = employee.name
        role = compact_role(employee.role)
        avatar = initials(employee.name)

    st.markdown(
        f"""
        <div class="aisha-topbar">
          <div class="aisha-topbar-inner">
            <div class="aisha-brand">
              <div class="aisha-logo">A</div>
              <div>
                <div class="aisha-brand-title">AISHA</div>
                <div class="aisha-brand-subtitle">AI Support for Hires and Associates</div>
              </div>
            </div>
            <div class="aisha-topbar-note">{escape(SHORT_DISCLAIMER)}</div>
            <div class="aisha-persona-pill">
              <div class="aisha-avatar">{escape(avatar)}</div>
              <div>
                <div class="aisha-persona-name">{escape(name)}</div>
                <div class="aisha-persona-role">{escape(role)}</div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def demo_persona_short_label(pid: str, employees: list[Employee]) -> str:
    if pid == HR_ADMIN:
        return "HR"
    employee = next(e for e in employees if e.id == pid)
    return employee.first_name


def render_demo_controls(employees: list[Employee]) -> None:
    st.markdown(
        """
        <div class="aisha-demo-strip">
          <div class="aisha-demo-strip-inner">
            <div class="aisha-demo-label">Demo controls</div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([0.50, 0.22, 0.28], vertical_alignment="center")
    valid_personas = [employee.id for employee in employees] + [HR_ADMIN]
    with c1:
        selected = st.segmented_control(
            "Persona",
            valid_personas,
            default=st.session_state["persona_id"],
            format_func=lambda pid: demo_persona_short_label(pid, employees),
            label_visibility="collapsed",
            key="persona_picker",
        )
        if selected and selected != st.session_state["persona_id"]:
            st.session_state["persona_id"] = selected
            st.rerun()
    with c2:
        st.date_input(
            "Simulated date",
            key="sim_date",
            label_visibility="collapsed",
            help=(
                "Demo prop: drives ramp stage labels and weekly pulse "
                "check-in timing."
            ),
        )
    with c3:
        if st.button("Reset demo data", type="secondary", use_container_width=True):
            reset_demo()
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_legacy_demo_controls(employees: list[Employee]) -> None:
    with st.expander(":material/tune: Backstage demo controls", expanded=False):
        c1, c2, c3 = st.columns([2.4, 1.2, 1])
        with c1:
            st.selectbox(
                "Persona",
                [employee.id for employee in employees] + [HR_ADMIN],
                format_func=lambda pid: persona_label(pid, employees),
                key="persona_id",
                help=(
                    "Prototype stand-in for SSO. Production would identify "
                    "people from company login."
                ),
            )
        with c2:
            st.date_input(
                "Simulated date",
                key="sim_date",
                help=(
                    "Demo prop: drives ramp stage labels and weekly pulse "
                    "check-in timing."
                ),
            )
        with c3:
            st.write("")
            st.write("")
            if st.button("Reset demo data", type="secondary"):
                reset_demo()
        st.caption(
            f"Local models: agent `{settings.agent_model}`, guardrail "
            f"`{settings.guardrail_model}`, embeddings `{settings.embed_model}`."
        )


def reset_demo() -> None:
    get_repo.clear()
    kb_ready.clear()
    settings.db_path.unlink(missing_ok=True)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def stage_rail_html(current_key: str) -> str:
    current_idx = PHASE_ORDER.index(current_key)
    parts = ['<div class="aisha-stage-rail">']
    for idx, key in enumerate(PHASE_ORDER):
        state = "done" if idx < current_idx else "current" if idx == current_idx else ""
        label = PHASE_LABELS[key]
        short = (
            label.replace("Day 1 Setup", "Day 1")
            .replace("Week 1 Foundations", "Week 1")
            .replace("Week 2 Practice and Feedback", "Week 2")
            .replace("Day 30 Readiness Check", "Day 30")
        )
        parts.append(
            "<div class=\"aisha-stage-segment\">"
            f"<div class=\"aisha-stage-bar {state}\"></div>"
            f"<div class=\"aisha-stage-label {state}\">{escape(short)}</div>"
            "</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def render_readiness_summary(employee: Employee, sim_date: date, repo: Repo) -> None:
    done, total = repo.progress(employee.id)
    pct = progress_percent(done, total)
    phase_key = current_phase_key(employee, sim_date)
    phase_label = PHASE_LABELS[phase_key]
    hero = (
        f"Getting {employee.first_name} ready for the Day 30 readiness "
        "conversation."
    )
    st.markdown(
        f"""
        <section class="aisha-hero">
          <div class="aisha-eyebrow">Goal · Day 30 readiness</div>
          <h1>{escape(hero)}</h1>
          <div class="aisha-hero-meta">
            Current stage: <strong>{escape(phase_label)}</strong> ·
            {done} of {total} real ramp tasks done · <strong>{pct}%</strong>
          </div>
          <div class="aisha-progress-track">
            <div class="aisha-progress-fill" style="width: {pct}%;"></div>
          </div>
          {stage_rail_html(phase_key)}
        </section>
        """,
        unsafe_allow_html=True,
    )


def complete_task_and_rerun(repo: Repo, employee_id: str, item_id: int) -> None:
    item = repo.complete_task(employee_id, item_id)
    if item:
        st.toast(f"Marked done: {item.title}")
    st.rerun()


def render_next_up(employee: Employee, open_items: list[ChecklistItem], repo: Repo) -> None:
    with st.container(border=True):
        st.markdown(
            """
            <div class="aisha-card-heading">
              <h2>Next up</h2>
              <span class="aisha-section-note">Open tasks on your ramp plan</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not open_items:
            st.success(
                "Everything in the ramp plan is marked done.",
                icon=":material/check_circle:",
            )
            return

        for item in open_items[:3]:
            c_id, c_text, c_action = st.columns(
                [0.12, 0.68, 0.20], vertical_alignment="center"
            )
            c_id.markdown(
                f'<div class="aisha-task-id">#{item.id}</div>',
                unsafe_allow_html=True,
            )
            c_text.markdown(
                f'<div class="aisha-task-title">{escape(item.title)}</div>',
                unsafe_allow_html=True,
            )
            c_text.caption(f"{PHASE_LABELS.get(item.phase, item.phase)} · Not yet marked done")
            if c_action.button(
                "Mark done",
                key=f"complete_task_{employee.id}_{item.id}",
                type="secondary",
                use_container_width=True,
            ):
                complete_task_and_rerun(repo, employee.id, item.id)


def file_support_escalation(repo: Repo, employee: Employee, item: ChecklistItem) -> None:
    repo.add_escalation(
        employee.id,
        question=f"Help needed with task #{item.id}: {item.title}",
        details=(
            "Filed by the new hire from the AISHA cockpit because this open "
            "ramp task may be blocking progress."
        ),
    )
    st.toast("Support escalation filed with People Experience.")
    st.rerun()


def render_blockers(
    employee: Employee,
    blockers: list[dict],
    repo: Repo,
) -> None:
    if not blockers:
        return
    with st.container(border=True):
        st.markdown(
            """
            <div class="aisha-card-heading">
              <h2>Blocked · needs help</h2>
              <span class="aisha-section-note">Based on open tasks or help requests.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for blocker in blockers:
            helper: Person | None = blocker.get("helper")
            helper_text = (
                f"{helper.name} · {helper.role}" if helper else "People Experience"
            )
            c_text, c_action = st.columns([0.72, 0.28], vertical_alignment="center")
            c_text.markdown(f"**{blocker['title']}**")
            c_text.caption(
                f"{blocker['state']} · {blocker['description']} · Can help: {helper_text}"
            )
            if blocker["kind"] == "task":
                item = blocker["item"]
                if c_action.button(
                    "File support escalation",
                    key=f"escalate_task_{employee.id}_{item.id}",
                    type="primary",
                    use_container_width=True,
                ):
                    file_support_escalation(repo, employee, item)
            else:
                c_action.info("Open help request", icon=":material/support_agent:")


def render_helpers(employee: Employee, open_items: list[ChecklistItem]) -> None:
    helpers = helper_list(employee, open_items)
    with st.container(border=True):
        st.markdown(
            """
            <div class="aisha-card-heading">
              <h2>Who can help</h2>
              <span class="aisha-section-note">People mapped from the seeded org directory.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not helpers:
            st.info(
                "No org contacts found in the seeded directory.",
                icon=":material/person_search:",
            )
            return
        chips = []
        for helper in helpers[:6]:
            chips.append(
                f"""
                <div class="aisha-person-chip">
                  <div class="aisha-person-avatar">{escape(initials(helper.name))}</div>
                  <div>
                    <div class="aisha-person-name">{escape(helper.name)}</div>
                    <div class="aisha-person-role">{escape(helper.role)} · {escape(helper.team)}</div>
                  </div>
                </div>
                """
            )
        st.markdown(
            f'<div class="aisha-people-grid">{"".join(chips)}</div>',
            unsafe_allow_html=True,
        )


def build_prompt_chips(
    employee: Employee,
    open_items: list[ChecklistItem],
    blockers: list[dict],
) -> list[tuple[str, str]]:
    chips: list[tuple[str, str]] = [
        ("Next task", "What should I do next on my ramp plan?"),
        (
            "Day 30 readiness",
            f"What does Day 30 readiness mean for my role as {employee.role}?",
        ),
        ("Who can help?", "Who can help with my current open tasks?"),
    ]
    if blockers:
        chips.insert(0, ("Unblock me", f"Help me unblock: {blockers[0]['title']}"))
    if any(text_has_any(item.title, {"aml", "privacy", "compliance"}) for item in open_items):
        chips.append(
            (
                "Compliance basics",
                "What should I know about AML, privacy, and customer confidentiality for Day 30?",
            )
        )
    else:
        chips.append(
            (
                "Manager check-in",
                "What should I prepare before my manager check-in?",
            )
        )
    return chips[:5]


def queue_prompt(employee_id: str, prompt: str) -> None:
    st.session_state[f"queued_prompt_{employee_id}"] = prompt
    st.rerun()


def render_sources(sources: list[dict]) -> None:
    names: list[str] = []
    for source in sources:
        source_name = source.get("source", "unknown")
        if source_name not in names:
            names.append(source_name)
    with st.expander(f":material/menu_book: Sources ({len(names)})"):
        for source in sources:
            st.markdown(f"**{source.get('source', 'unknown')}** - {source.get('title', '')}")
            snippet = source.get("snippet", "").strip()
            if snippet:
                st.caption(snippet + "...")


def show_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            render_sources(msg["sources"])


def to_lc_messages(msgs: list[dict], limit: int = 12) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for msg in msgs[-limit:]:
        if msg["role"] == "user":
            out.append(HumanMessage(msg["content"]))
        else:
            out.append(AIMessage(msg["content"]))
    return out


def ensure_chat_state(employee: Employee, repo: Repo, sim_date: date) -> list[dict]:
    msgs_key = f"messages_{employee.id}"
    asked_key = f"pulse_asked_{employee.id}"
    pending_key = f"pulse_pending_{employee.id}"
    if msgs_key not in st.session_state:
        persisted = repo.list_chat_messages(employee.id)
        if persisted:
            st.session_state[msgs_key] = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    **({"kind": msg.kind} if msg.kind else {}),
                    **({"sources": msg.sources} if msg.sources else {}),
                }
                for msg in persisted
            ]
            if persisted[-1].kind == "checkin":
                st.session_state[asked_key] = sim_date.isoformat()
                st.session_state[pending_key] = True
        else:
            greeting = (
                f"Hi {employee.first_name}! I'm **AISHA**, your onboarding and "
                "ramp support assistant for this fictionalized BDO educational "
                "demo. Ask me about your ramp plan, Day 30 readiness, access "
                "blockers, policies, or who can help."
            )
            repo.add_chat_message(employee.id, "assistant", greeting)
            st.session_state[msgs_key] = [{"role": "assistant", "content": greeting}]
    return st.session_state[msgs_key]


def maybe_add_pulse_checkin(
    employee: Employee,
    repo: Repo,
    sim_date: date,
    messages: list[dict],
) -> None:
    asked_key = f"pulse_asked_{employee.id}"
    pending_key = f"pulse_pending_{employee.id}"
    if pulse.is_checkin_due(
        employee.start_date,
        sim_date,
        repo.last_checkin_date(employee.id),
    ) and st.session_state.get(asked_key) != sim_date.isoformat():
        checkin_question = pulse.build_checkin_question(employee, sim_date)
        messages.append(
            {"role": "assistant", "content": checkin_question, "kind": "checkin"}
        )
        repo.add_chat_message(employee.id, "assistant", checkin_question, kind="checkin")
        st.session_state[asked_key] = sim_date.isoformat()
        st.session_state[pending_key] = True


def render_prompt_chips(
    employee: Employee,
    open_items: list[ChecklistItem],
    blockers: list[dict],
) -> None:
    st.markdown('<div class="aisha-mini-label">Prompt chips</div>', unsafe_allow_html=True)
    chips = build_prompt_chips(employee, open_items, blockers)
    cols = st.columns(len(chips))
    for idx, (label, prompt) in enumerate(chips):
        if cols[idx].button(label, key=f"chip_{employee.id}_{idx}", type="secondary"):
            queue_prompt(employee.id, prompt)


def render_chat_panel(
    employee: Employee,
    repo: Repo,
    sim_date: date,
    open_items: list[ChecklistItem],
    blockers: list[dict],
) -> None:
    with st.container(border=True):
        st.markdown(
            """
            <div class="aisha-chat-heading">
              <div class="aisha-logo">A</div>
              <div>
                <div class="aisha-chat-title">Ask AISHA</div>
                <div class="aisha-chat-subtitle">Knows your ramp plan and the handbook</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="aisha-chat-body-note">Grounded chat with your ramp plan, tools, people lookup, and handbook sources.</div>',
            unsafe_allow_html=True,
        )
        if not kb_ready():
            st.warning(
                "The handbook knowledge base is empty - run "
                "`uv run python -m stai.ingestion` once, then reload.",
                icon=":material/database:",
            )

        messages = ensure_chat_state(employee, repo, sim_date)
        maybe_add_pulse_checkin(employee, repo, sim_date, messages)

        for msg in messages:
            show_message(msg)

        st.markdown('<div class="aisha-composer">', unsafe_allow_html=True)
        render_prompt_chips(employee, open_items, blockers)
        st.markdown("</div>", unsafe_allow_html=True)
        queued = st.session_state.pop(f"queued_prompt_{employee.id}", None)
        with st.form(f"chat_form_{employee.id}", clear_on_submit=True):
            c_input, c_send = st.columns([0.84, 0.16], vertical_alignment="center")
            typed = c_input.text_input(
                "Ask AISHA",
                placeholder="Ask about your ramp, tasks, policies, or who can help...",
                label_visibility="collapsed",
            )
            submitted = c_send.form_submit_button("↑", use_container_width=True)

    prompt = queued or (typed.strip() if submitted and typed.strip() else "")
    if not prompt:
        return

    messages.append({"role": "user", "content": prompt})
    repo.add_chat_message(employee.id, "user", prompt)
    show_message(messages[-1])

    turn_started = time.perf_counter()
    pending_key = f"pulse_pending_{employee.id}"
    was_pulse_reply = st.session_state.pop(pending_key, False)
    if was_pulse_reply:
        with st.spinner("Recording your check-in..."):
            result = pulse.classify_pulse(prompt)
        repo.add_pulse(employee.id, sim_date, result, raw_reply=prompt)
        st.toast(f"Check-in recorded (sentiment {result.sentiment}/5)")

    if not was_pulse_reply:
        with st.spinner("Checking topic..."):
            verdict = classify_input(prompt)
        if not verdict.allowed:
            refusal = REFUSALS[verdict.category]
            messages.append({"role": "assistant", "content": refusal, "kind": "refusal"})
            repo.add_chat_message(employee.id, "assistant", refusal, kind="refusal")
            log_turn(
                TurnRecord(
                    route="streamlit",
                    employee_id=employee.id,
                    agent_model=settings.agent_model,
                    guardrail_model=settings.guardrail_model,
                    message_chars=len(prompt),
                    guardrail_category=verdict.category,
                    refused=True,
                    latency_ms=int((time.perf_counter() - turn_started) * 1000),
                )
            )
            show_message(messages[-1])
            return

    agent, capture = build_agent(employee, repo, sim_date)
    history = to_lc_messages(messages)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        streamed = ""
        try:
            with st.spinner("Thinking..."):
                for token in stream_agent_text(agent, history):
                    streamed += token
                    placeholder.markdown(streamed + "...")
        except Exception as exc:
            placeholder.empty()
            st.error(
                "I couldn't reach the local model. Is Ollama running and are "
                f"`{settings.agent_model}` / `{settings.guardrail_model}` pulled?\n\n"
                f"`{exc}`"
            )
            log_turn(
                TurnRecord(
                    route="streamlit",
                    employee_id=employee.id,
                    agent_model=settings.agent_model,
                    guardrail_model=settings.guardrail_model,
                    message_chars=len(prompt),
                    latency_ms=int((time.perf_counter() - turn_started) * 1000),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            messages.pop()
            return

        grounded = apply_output_guardrails(
            streamed,
            capture.used_search,
            capture.source_names,
        )
        placeholder.markdown(grounded.answer)
        if capture.sources:
            render_sources(capture.sources)

    messages.append(
        {
            "role": "assistant",
            "content": grounded.answer,
            "sources": capture.sources or None,
        }
    )
    repo.add_chat_message(
        employee.id,
        "assistant",
        grounded.answer,
        sources=capture.sources,
    )
    log_turn(
        TurnRecord(
            route="streamlit",
            employee_id=employee.id,
            agent_model=settings.agent_model,
            guardrail_model=settings.guardrail_model,
            message_chars=len(prompt),
            answer_chars=len(grounded.answer),
            est_input_tokens=estimate_tokens(prompt),
            est_output_tokens=estimate_tokens(grounded.answer),
            latency_ms=int((time.perf_counter() - turn_started) * 1000),
            guardrail_category="" if was_pulse_reply else "on_topic",
            tools_used=list(capture.tool_calls),
            sources=capture.source_names,
            escalation_id=capture.escalation_id,
            plan_changed=capture.plan_changed,
        )
    )
    if capture.escalation_id:
        st.toast(f"Escalation #{capture.escalation_id} filed - visible to People Experience.")
    if capture.plan_changed:
        st.rerun()


def render_new_hire_cockpit(
    employee: Employee,
    repo: Repo,
    sim_date: date,
    open_escalations: list[Escalation],
) -> None:
    st.markdown(
        (
            '<div class="aisha-page-kicker">'
            f"Day 30 readiness cockpit · {escape(employee.role)} · "
            f"{escape(employee.department)} · start date {employee.start_date:%b %d, %Y}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    items = repo.list_plan_items(employee.id)
    open_items = [item for item in items if not item.done]
    blockers = make_blockers(employee, open_items, open_escalations)

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        render_readiness_summary(employee, sim_date, repo)
        render_next_up(employee, open_items, repo)
        render_blockers(employee, blockers, repo)
        render_helpers(employee, open_items)
    with right:
        render_chat_panel(employee, repo, sim_date, open_items, blockers)


def latest_pulse_label(record: PulseRecord | None) -> str:
    return f"{record.sentiment}/5" if record else "No check-in yet"


def render_metric(label: str, value: str | int, help_text: str = "") -> None:
    st.metric(label, value, help=help_text, border=True)


def render_support_cards(profiles: list[dict]) -> None:
    st.subheader("May need support")
    st.caption("Signals are derived from tasks, pulse trends, and explicit help requests.")
    flagged = [profile for profile in profiles if profile["needs_support"]]
    if not flagged:
        st.success(
            "No current support signals from tasks, pulse records, or open help requests.",
            icon=":material/check_circle:",
        )
        return

    for profile in flagged:
        employee: Employee = profile["employee"]
        signal_items = "".join(
            f"<li>{escape(signal)}</li>" for signal in profile["signals"]
        )
        st.markdown(
            f"""
            <section class="aisha-support-card">
              <div class="aisha-support-card-head">
                <div style="display:flex;align-items:center;gap:11px;min-width:0;">
                  <div class="aisha-person-avatar">{escape(initials(employee.name))}</div>
                  <div style="min-width:0;">
                    <div class="aisha-person-name">{escape(employee.name)}</div>
                    <div class="aisha-person-role">{escape(employee.role)} · {escape(profile["stage"])}</div>
                  </div>
                </div>
                <span class="aisha-status-pill">May need support</span>
              </div>
              <div class="aisha-mini-label">Signals</div>
              <ul class="aisha-signal-list">{signal_items}</ul>
              <div class="aisha-action-note">{escape(profile["action"])}</div>
              <div class="aisha-privacy-note">
                Privacy note: summary from tasks, pulse, and escalations. No private chat transcript shown.
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )


def render_help_requests(
    repo: Repo,
    open_escalations: list[Escalation],
) -> None:
    st.subheader("Explicit help requests")
    st.caption("Escalations hires filed on purpose.")
    if not open_escalations:
        st.info("No open help requests.", icon=":material/task_alt:")
        return
    for escalation in open_escalations:
        employee = repo.get_employee(escalation.employee_id)
        with st.container(border=True):
            c_text, c_action = st.columns([0.76, 0.24], vertical_alignment="center")
            c_text.markdown(
                f"**#{escalation.id} · {employee.name if employee else escalation.employee_id}**"
            )
            c_text.write(escalation.question)
            if escalation.details:
                c_text.caption(escalation.details)
            c_text.caption(f"Filed {escalation.created_at:%b %d, %H:%M}")
            if c_action.button(
                "Mark resolved",
                key=f"resolve_escalation_{escalation.id}",
                type="secondary",
            ):
                repo.resolve_escalation(escalation.id)
                st.toast(f"Resolved help request #{escalation.id}")
                st.rerun()


def render_pulse_cards(profiles: list[dict]) -> None:
    st.subheader("Pulse & support signals")
    st.caption("Latest score, trend, concern tags, and privacy-preserving summary.")
    cols = st.columns(3)
    for idx, profile in enumerate(profiles):
        employee: Employee = profile["employee"]
        latest: PulseRecord | None = profile["latest_pulse"]
        with cols[idx % 3], st.container(border=True):
            st.markdown(f"**{employee.name}**")
            if latest is None:
                st.info("No check-in yet.", icon=":material/event_repeat:")
                continue
            st.metric("Latest pulse", f"{latest.sentiment}/5")
            st.caption(f"Trend: {profile['pulse_trend']}")
            if latest.concerns:
                st.markdown(" ".join(f"`{tag}`" for tag in latest.concerns))
            else:
                st.caption("No concern tags")
            if latest.summary:
                st.caption(f"Summary: {latest.summary}")


def render_all_hires_table(profiles: list[dict]) -> None:
    with st.expander("All hires - drill-down", expanded=False):
        rows = []
        for profile in profiles:
            employee: Employee = profile["employee"]
            rows.append(
                {
                    "Hire": employee.name,
                    "Role": employee.role,
                    "Stage": profile["stage"],
                    "Progress": progress_ratio(profile["done"], profile["total"]),
                    "Latest pulse": latest_pulse_label(profile["latest_pulse"]),
                    "Trend/status": (
                        "May need support"
                        if profile["needs_support"]
                        else profile["pulse_trend"]
                        if profile["pulse_trend"] != "-"
                        else "Steady"
                    ),
                }
            )
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            column_config={
                "Progress": st.column_config.ProgressColumn(
                    "Progress",
                    min_value=0.0,
                    max_value=1.0,
                    format="percent",
                ),
            },
        )


def render_dashboard(
    employees: list[Employee],
    repo: Repo,
    sim_date: date,
    open_escalations: list[Escalation],
) -> None:
    st.header("People Experience · Support Console")
    st.caption("Enough signal to offer help, not enough detail to police.")
    st.caption(f"Simulated date {sim_date:%B %d, %Y} · {SHORT_DISCLAIMER}")

    profiles = build_support_profiles(employees, repo, sim_date, open_escalations)
    support_count = sum(1 for profile in profiles if profile["needs_support"])

    st.markdown(
        f"""
        <div class="aisha-metric-grid">
          <div class="aisha-metric-card">
            <div class="aisha-metric-value">{len(employees)}</div>
            <div class="aisha-metric-label">Hires ramping</div>
          </div>
          <div class="aisha-metric-card warn">
            <div class="aisha-metric-value">{support_count}</div>
            <div class="aisha-metric-label">May need support</div>
          </div>
          <div class="aisha-metric-card">
            <div class="aisha-metric-value">{len(open_escalations)}</div>
            <div class="aisha-metric-label">Open help requests</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    primary, explicit = st.columns([1.15, 1], gap="large")
    with primary:
        render_support_cards(profiles)
    with explicit:
        render_help_requests(repo, open_escalations)

    render_pulse_cards(profiles)
    render_all_hires_table(profiles)


def main() -> None:
    inject_css()
    repo = get_repo()
    employees = repo.list_employees()
    if not employees:
        st.error("No employees found. Reset demo data or check data/employees.json.")
        return

    valid_personas = [employee.id for employee in employees] + [HR_ADMIN]
    if st.session_state.get("persona_id") not in valid_personas:
        st.session_state["persona_id"] = employees[0].id
    if "sim_date" not in st.session_state:
        st.session_state["sim_date"] = default_sim_date(employees)

    render_top_bar(st.session_state["persona_id"], employees)
    render_demo_controls(employees)

    persona_id = st.session_state["persona_id"]
    sim_date = st.session_state["sim_date"]
    open_escalations = repo.list_escalations(status="open")

    if persona_id == HR_ADMIN:
        render_dashboard(employees, repo, sim_date, open_escalations)
    else:
        employee = next(e for e in employees if e.id == persona_id)
        render_new_hire_cockpit(employee, repo, sim_date, open_escalations)

    st.markdown(
        (
            '<p class="aisha-footer">'
            "All employee records, documents, contacts, metrics, and interactions "
            "are fictionalized for storytelling and evaluation. AISHA is support, "
            "not surveillance."
            "</p>"
        ),
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
