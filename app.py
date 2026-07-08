"""STAI - Streamlit entry point for the AISHA educational demo.

Two views behind a sidebar persona picker:
- New hire: chat with the onboarding and ramp agent.
- HR admin: support dashboard for hires, pulse trends, and escalations.

Run: uv run streamlit run app.py
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from stai import pulse
from stai.agent import build_agent, stream_agent_text
from stai.config import settings
from stai.guardrails import REFUSALS, apply_output_guardrails, classify_input
from stai.models import Employee
from stai.state import Repo

st.set_page_config(
    page_title="STAI - AISHA BDO educational demo",
    page_icon=":material/support_agent:",
    layout="wide",
)

HR_ADMIN = "hr_admin"
DISCLAIMER = (
    "AISHA is an educational capstone prototype. It is not affiliated with, "
    "endorsed by, or representative of BDO Unibank. All records, contacts, "
    "documents, metrics, and interactions in this demo are fictionalized."
)


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


repo = get_repo()
employees = repo.list_employees()


def persona_label(pid: str) -> str:
    if pid == HR_ADMIN:
        return "HR admin - People Experience"
    emp = next(e for e in employees if e.id == pid)
    return f"{emp.name} - {emp.role}"


with st.sidebar:
    st.title(":material/support_agent: AISHA")
    st.caption("AI Support for Hires and Associates - local-first onboarding and ramp support.")
    st.caption(DISCLAIMER)

    persona_id = st.selectbox(
        "Signed in as",
        [e.id for e in employees] + [HR_ADMIN],
        format_func=persona_label,
        help="Prototype stand-in for SSO. Production would identify employees from company login.",
    )
    sim_date = st.date_input(
        "Simulated date",
        value=date.today(),
        help=(
            "Demo prop: drives the weekly pulse check-in schedule. "
            "Jump a week forward and AISHA opens with a check-in."
        ),
    )

    st.divider()
    if persona_id != HR_ADMIN:
        emp = next(e for e in employees if e.id == persona_id)
        done, total = repo.progress(emp.id)
        st.caption(
            f"{emp.name} | {emp.department} | started {emp.start_date:%b %d} | "
            f"week {pulse.weeks_since_start(emp.start_date, sim_date) + 1} of ramp"
        )
        st.progress(done / total if total else 0.0, text=f"Ramp progress: {done}/{total} tasks done")

    with st.expander(":material/settings: Demo controls"):
        st.caption(
            f"Agent `{settings.agent_model}` | guardrail `{settings.guardrail_model}` | "
            f"embeddings `{settings.embed_model}` - all env-swappable (STAI_*)."
        )
        if st.button("Reset demo data", width="stretch"):
            get_repo.clear()
            kb_ready.clear()
            settings.db_path.unlink(missing_ok=True)
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


SUGGESTIONS = [
    "What do I need to do before my first day?",
    "What is my Day 30 Readiness Check?",
    "Who do I ask about laptop or system access?",
    "I feel behind on branch shadowing - what should I do?",
]


def to_lc_messages(msgs: list[dict], limit: int = 12) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in msgs[-limit:]:
        if m["role"] == "user":
            out.append(HumanMessage(m["content"]))
        else:
            out.append(AIMessage(m["content"]))
    return out


def render_sources(sources: list[dict]) -> None:
    names = []
    for s in sources:
        if s["source"] not in names:
            names.append(s["source"])
    with st.expander(f":material/menu_book: Sources ({len(names)})"):
        for s in sources:
            st.markdown(f"**{s['source']}** - {s['title']}")
            st.caption(s["snippet"] + "...")


def show_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            render_sources(msg["sources"])


def render_chat(employee: Employee) -> None:
    st.header(f"Welcome, {employee.first_name} :material/waving_hand:")
    st.caption(
        "AISHA helps with fictionalized BDO onboarding, ramp tasks, policy lookup, "
        "people routing, and Day 30 readiness support."
    )
    if not kb_ready():
        st.warning(
            "The handbook knowledge base is empty - run "
            "`uv run python -m stai.ingestion` once, then reload.",
            icon=":material/database:",
        )

    msgs_key = f"messages_{employee.id}"
    if msgs_key not in st.session_state:
        st.session_state[msgs_key] = [
            {
                "role": "assistant",
                "content": (
                    f"Hi {employee.first_name}! I'm **AISHA**, your onboarding and ramp "
                    "support assistant for this fictionalized BDO educational demo. "
                    "Ask me about your ramp plan, branch readiness, payslips, benefits, "
                    "policies, access blockers, or who can help."
                ),
            }
        ]
    messages: list[dict] = st.session_state[msgs_key]

    asked_key = f"pulse_asked_{employee.id}"
    pending_key = f"pulse_pending_{employee.id}"
    if pulse.is_checkin_due(
        employee.start_date, sim_date, repo.last_checkin_date(employee.id)
    ) and st.session_state.get(asked_key) != sim_date.isoformat():
        messages.append(
            {
                "role": "assistant",
                "content": pulse.build_checkin_question(employee, sim_date),
                "kind": "checkin",
            }
        )
        st.session_state[asked_key] = sim_date.isoformat()
        st.session_state[pending_key] = True

    for msg in messages:
        show_message(msg)

    queued = st.session_state.pop("queued_prompt", None)
    if len(messages) <= 1 and not queued:
        selected = st.pills("Try asking", SUGGESTIONS, label_visibility="collapsed")
        if selected:
            st.session_state.queued_prompt = selected
            st.rerun()

    prompt = st.chat_input(
        "Ask about policies, access, your ramp plan, or who can help...",
        submit_mode="disable",
    )
    prompt = prompt or queued
    if not prompt:
        return

    messages.append({"role": "user", "content": prompt})
    show_message(messages[-1])

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
            messages.pop()
            return

        grounded = apply_output_guardrails(
            streamed, capture.used_search, capture.source_names
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
    if capture.escalation_id:
        st.toast(
            f"Escalation #{capture.escalation_id} filed - visible in the HR view"
        )
    if capture.plan_changed:
        st.rerun()


def render_dashboard() -> None:
    st.header("HR support dashboard :material/monitoring:")
    st.caption(f"Fictionalized BDO educational demo | simulated date {sim_date:%B %d, %Y}")
    st.caption("AISHA shows support signals, not private chat transcripts by default.")

    rows = []
    support_needed = 0
    for emp in employees:
        done, total = repo.progress(emp.id)
        history = repo.pulse_history(emp.id)
        scores = [r.sentiment for r in history]
        needs_support = pulse.risk_flag(scores)
        support_needed += needs_support
        rows.append(
            {
                "Hire": emp.name,
                "Role": emp.role,
                "Started": emp.start_date,
                "Ramp progress": (done / total) if total else 0.0,
                "Last pulse": f"{scores[-1]}/5" if scores else "-",
                "Pulse history": scores or None,
                "Trend": pulse.trend(scores),
                "Support signal": "Needs support" if needs_support else "On track",
            }
        )

    open_escalations = repo.list_escalations(status="open")
    all_progress = [r["Ramp progress"] for r in rows]
    avg_progress = round(100 * sum(all_progress) / len(all_progress)) if rows else 0

    with st.container(horizontal=True):
        st.metric("Active new hires", len(employees), border=True)
        st.metric("Avg ramp progress", f"{avg_progress}%", border=True)
        st.metric("Open escalations", len(open_escalations), border=True)
        st.metric(
            "Support signals",
            support_needed,
            delta="needs attention" if support_needed else "all clear",
            delta_color="inverse" if support_needed else "normal",
            border=True,
        )

    with st.container(border=True):
        st.subheader("New hires")
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            column_config={
                "Started": st.column_config.DateColumn("Started", format="MMM DD"),
                "Ramp progress": st.column_config.ProgressColumn(
                    "Ramp progress", min_value=0.0, max_value=1.0, format="percent"
                ),
                "Pulse history": st.column_config.LineChartColumn(
                    "Pulse history",
                    y_min=1,
                    y_max=5,
                    help="Weekly check-in sentiment, 1-5",
                ),
            },
        )
        st.caption(
            "Support signal = latest pulse <= 2, or declining and <= 3. "
            "The dashboard summarizes support needs without showing raw private chat by default."
        )

    col_pulse, col_esc = st.columns(2)

    with col_pulse, st.container(border=True):
        st.subheader("Pulse detail")
        emp = st.selectbox(
            "Hire", employees, format_func=lambda e: e.name, key="pulse_detail_hire"
        )
        history = repo.pulse_history(emp.id)
        if not history:
            st.info(
                "No check-ins yet. Pulses appear after the first weekly check-in - "
                "move the simulated date a week past the start date and answer as the hire.",
                icon=":material/event_repeat:",
            )
        else:
            frame = pd.DataFrame(
                {
                    "Check-in": [r.checkin_date for r in history],
                    "Sentiment": [r.sentiment for r in history],
                }
            )
            import altair as alt

            chart = (
                alt.Chart(frame)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Check-in:T", title="Check-in date"),
                    y=alt.Y("Sentiment:Q", scale=alt.Scale(domain=[1, 5]), title="Sentiment (1-5)"),
                    tooltip=["Check-in:T", "Sentiment:Q"],
                )
            )
            st.altair_chart(chart)
            latest = history[-1]
            if latest.concerns:
                st.markdown(
                    "Latest concern tags: " + " ".join(f"`{c}`" for c in latest.concerns)
                )
            with st.expander("Check-in summaries"):
                st.dataframe(
                    pd.DataFrame(
                        {
                            "Date": [r.checkin_date for r in history],
                            "Sentiment": [r.sentiment for r in history],
                            "Concerns": [", ".join(r.concerns) for r in history],
                            "Summary": [r.summary for r in history],
                        }
                    ),
                    hide_index=True,
                )

    with col_esc, st.container(border=True):
        st.subheader("Escalation queue")
        if not open_escalations:
            st.info("No open escalations.", icon=":material/task_alt:")
        for esc in open_escalations:
            emp = repo.get_employee(esc.employee_id)
            with st.container(border=True):
                st.markdown(f"**#{esc.id} | {emp.name if emp else esc.employee_id}**")
                st.markdown(esc.question)
                if esc.details:
                    st.caption(esc.details)
                st.caption(f"Filed {esc.created_at:%b %d, %H:%M}")
                st.button(
                    "Mark resolved",
                    key=f"resolve_{esc.id}",
                    icon=":material/check:",
                    on_click=repo.resolve_escalation,
                    args=(esc.id,),
                )
        resolved = repo.list_escalations(status="resolved")
        if resolved:
            with st.expander(f"Resolved ({len(resolved)})"):
                for esc in resolved:
                    emp = repo.get_employee(esc.employee_id)
                    st.markdown(
                        f"Done **#{esc.id}** ({emp.name if emp else esc.employee_id}) - {esc.question}"
                    )


if persona_id == HR_ADMIN:
    render_dashboard()
else:
    render_chat(next(e for e in employees if e.id == persona_id))
