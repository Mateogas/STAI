"""STAI — Streamlit entry point.

Two views behind a sidebar persona picker (production would sit behind SSO —
see docs/BUSINESS_CASE.md):
- New hire  : chat with the onboarding agent (streaming, citations, plan bar)
- HR admin  : dashboard of hires, pulse/risk flags, escalation queue

Run:  uv run streamlit run app.py
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
    page_title="STAI — Meridian Labs onboarding",
    page_icon=":material/explore:",
    layout="wide",
)

HR_ADMIN = "hr_admin"


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


# --------------------------------------------------------------------- sidebar

def persona_label(pid: str) -> str:
    if pid == HR_ADMIN:
        return "HR admin — People Ops"
    emp = next(e for e in employees if e.id == pid)
    return f"{emp.name} — {emp.role}"


with st.sidebar:
    st.title(":material/explore: STAI")
    st.caption("Meridian Labs onboarding assistant — runs fully local (Ollama + Chroma).")

    persona_id = st.selectbox(
        "Signed in as",
        [e.id for e in employees] + [HR_ADMIN],
        format_func=persona_label,
        help="Prototype stand-in for SSO — production identifies employees from company login.",
    )
    sim_date = st.date_input(
        "Simulated date",
        value=date.today(),
        help="Demo prop: drives the weekly pulse check-in schedule. "
        "Jump a week forward and the agent opens with a check-in.",
    )

    st.divider()
    if persona_id != HR_ADMIN:
        emp = next(e for e in employees if e.id == persona_id)
        done, total = repo.progress(emp.id)
        st.caption(
            f"{emp.name} · {emp.department} · started {emp.start_date:%b %d} · "
            f"week {pulse.weeks_since_start(emp.start_date, sim_date) + 1} of onboarding"
        )
        st.progress(done / total if total else 0.0, text=f"Plan: {done}/{total} tasks done")

    with st.expander(":material/settings: Demo controls"):
        st.caption(
            f"Agent `{settings.agent_model}` · guardrail `{settings.guardrail_model}` · "
            f"embeddings `{settings.embed_model}` — all env-swappable (STAI_*)."
        )
        if st.button("Reset demo data", width="stretch"):
            get_repo.clear()
            kb_ready.clear()
            settings.db_path.unlink(missing_ok=True)
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ------------------------------------------------------------------- chat view

SUGGESTIONS = [
    "What do I need to do before my first day?",
    "Explain my payslip deductions like it's my first job — it is",
    "Who do I ask about my laptop?",
    "¿Cuántos días de vacaciones tengo?",
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
            st.markdown(f"**{s['source']}** — {s['title']}")
            st.caption(s["snippet"] + "…")


def show_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            render_sources(msg["sources"])


def render_chat(employee: Employee) -> None:
    st.header(f"Welcome, {employee.first_name} :material/waving_hand:")
    if not kb_ready():
        st.warning(
            "The handbook knowledge base is empty — run "
            "`uv run python -m stai.ingestion` once, then reload.",
            icon=":material/database:",
        )

    msgs_key = f"messages_{employee.id}"
    if msgs_key not in st.session_state:
        st.session_state[msgs_key] = [
            {
                "role": "assistant",
                "content": (
                    f"Hi {employee.first_name}! I'm **Meri**, your onboarding assistant. "
                    "Ask me anything about Meridian Labs — benefits, payslips, policies, "
                    "your 30-60-90 plan, or who to talk to. No question is too basic; "
                    "everyone here asked the same ones once."
                ),
            }
        ]
    messages: list[dict] = st.session_state[msgs_key]

    # Proactive pulse: when a check-in is due at the simulated date, the agent
    # opens the session with the question (once per employee per sim date).
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

    # Suggestion chips on a fresh chat only.
    queued = st.session_state.pop("queued_prompt", None)
    if len(messages) <= 1 and not queued:
        selected = st.pills(
            "Try asking", SUGGESTIONS, label_visibility="collapsed"
        )
        if selected:
            st.session_state.queued_prompt = selected
            st.rerun()

    prompt = st.chat_input(
        "Ask about benefits, payroll, your plan, or the people here…",
        submit_mode="disable",
    )
    prompt = prompt or queued
    if not prompt:
        return

    messages.append({"role": "user", "content": prompt})
    show_message(messages[-1])

    # 1) Pulse reply: score + store, then let the agent respond with empathy.
    was_pulse_reply = st.session_state.pop(pending_key, False)
    if was_pulse_reply:
        with st.spinner("Recording your check-in…"):
            result = pulse.classify_pulse(prompt)
        repo.add_pulse(employee.id, sim_date, result, raw_reply=prompt)
        st.toast(f"Check-in recorded (sentiment {result.sentiment}/5)", icon="💙")

    # 2) Input guardrail (skipped for pulse replies — they answer our question).
    if not was_pulse_reply:
        with st.spinner("Checking topic…"):
            verdict = classify_input(prompt)
        if not verdict.allowed:
            refusal = REFUSALS[verdict.category]
            messages.append({"role": "assistant", "content": refusal, "kind": "refusal"})
            show_message(messages[-1])
            return

    # 3) Agent turn with streaming, then output guardrails on the final text.
    agent, capture = build_agent(employee, repo, sim_date)
    history = to_lc_messages(messages)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        streamed = ""
        try:
            with st.spinner("Thinking…"):
                for token in stream_agent_text(agent, history):
                    streamed += token
                    placeholder.markdown(streamed + "▌")
        except Exception as exc:
            placeholder.empty()
            st.error(
                "I couldn't reach the local model. Is Ollama running and are "
                f"`{settings.agent_model}` / `{settings.guardrail_model}` pulled?\n\n"
                f"`{exc}`"
            )
            messages.pop()  # drop the unanswered user turn so retry is clean
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
        st.toast(f"Escalation #{capture.escalation_id} filed — visible in the HR view", icon="📨")
    if capture.plan_changed:
        st.rerun()  # refresh the progress bar in the sidebar


# -------------------------------------------------------------- HR admin view

def render_dashboard() -> None:
    st.header("HR dashboard :material/monitoring:")
    st.caption(f"Meridian Labs · simulated date {sim_date:%B %d, %Y}")

    rows = []
    at_risk = 0
    for emp in employees:
        done, total = repo.progress(emp.id)
        history = repo.pulse_history(emp.id)
        scores = [r.sentiment for r in history]
        risky = pulse.risk_flag(scores)
        at_risk += risky
        rows.append(
            {
                "Hire": emp.name,
                "Role": emp.role,
                "Started": emp.start_date,
                "Plan progress": (done / total) if total else 0.0,
                "Last pulse": f"{scores[-1]}/5" if scores else "—",
                "Pulse history": scores or None,
                "Trend": pulse.trend(scores),
                "Status": "🚩 At risk" if risky else "🙂 OK",
            }
        )

    open_escalations = repo.list_escalations(status="open")
    all_progress = [r["Plan progress"] for r in rows]
    avg_progress = round(100 * sum(all_progress) / len(all_progress)) if rows else 0

    with st.container(horizontal=True):
        st.metric("Active new hires", len(employees), border=True)
        st.metric("Avg plan progress", f"{avg_progress}%", border=True)
        st.metric("Open escalations", len(open_escalations), border=True)
        st.metric(
            "At-risk hires",
            at_risk,
            delta="needs attention" if at_risk else "all clear",
            delta_color="inverse" if at_risk else "normal",
            border=True,
        )

    with st.container(border=True):
        st.subheader("New hires")
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            column_config={
                "Started": st.column_config.DateColumn("Started", format="MMM DD"),
                "Plan progress": st.column_config.ProgressColumn(
                    "Plan progress", min_value=0.0, max_value=1.0, format="percent"
                ),
                "Pulse history": st.column_config.LineChartColumn(
                    "Pulse history", y_min=1, y_max=5,
                    help="Weekly check-in sentiment, 1–5",
                ),
            },
        )
        st.caption(
            "🚩 = latest pulse ≤ 2, or declining and ≤ 3. Pulse = weekly agent "
            "check-in, sentiment-scored 1–5."
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
                "No check-ins yet. Pulses appear after the first weekly check-in — "
                "move the simulated date a week past the start date and answer as "
                "the hire.",
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
                    y=alt.Y("Sentiment:Q", scale=alt.Scale(domain=[1, 5]), title="Sentiment (1–5)"),
                    tooltip=["Check-in:T", "Sentiment:Q"],
                )
            )
            st.altair_chart(chart)
            latest = history[-1]
            if latest.concerns:
                st.markdown(
                    "Latest concerns: " + " ".join(f"`{c}`" for c in latest.concerns)
                )
            with st.expander("All check-ins (table view)"):
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
                st.markdown(f"**#{esc.id} · {emp.name if emp else esc.employee_id}**")
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
                        f"✔️ **#{esc.id}** ({emp.name if emp else esc.employee_id}) — {esc.question}"
                    )


# ------------------------------------------------------------------- dispatch

if persona_id == HR_ADMIN:
    render_dashboard()
else:
    render_chat(next(e for e in employees if e.id == persona_id))
