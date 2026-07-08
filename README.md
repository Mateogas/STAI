# STAI - AISHA Onboarding and Ramp Support Agent

AISHA means **AI Support for Hires and Associates**. STAI is the repo/course
codename; AISHA is the user-facing product story.

> AISHA is an educational capstone prototype. It is not affiliated with,
> endorsed by, or representative of BDO Unibank. All employee records,
> onboarding documents, org contacts, metrics, and demo interactions are
> fictionalized for storytelling and evaluation purposes.

AISHA is a local-first agentic onboarding and ramp-support assistant for a
fictionalized BDO educational demo. The main demo employee is **Alyssa Reyes**,
a **Management Trainee / Branch Banking Associate** ramping toward a **Day 30
Readiness Check** for supervised branch customer interactions.

Why this exists, who pays for it, and why agentic AI matters:
[`docs/BUSINESS_CASE.md`](docs/BUSINESS_CASE.md).

## What it does

| | Feature |
|---|---|
| Baseline | Grounded RAG Q&A over fictionalized onboarding docs, with citations |
| Baseline | Role-personalized onboarding and ramp plan the agent reads and updates |
| Baseline | People Experience escalation when the handbook has no answer |
| Baseline | HR support dashboard: progress, pulse trends, support signals, escalations |
| Differentiator | First-job decoder for payslips, benefits, jargon, and branch ramp expectations |
| Differentiator | Proactive pulse check-ins that surface support needs early |
| Differentiator | People routing for IT access, payroll, benefits, compliance learning, manager, buddy, and branch operations |
| Extra | Replies in the user's language; input/output guardrails for topic scope, injection, citations, and PII redaction |

## Ramp stages

AISHA does not frame onboarding as a long generic checklist. The fictional BDO
demo uses role-based onboarding and ramp stages:

- Pre-start
- Day 1 Setup
- Week 1 Foundations
- Week 2 Practice and Feedback
- Day 30 Readiness Check

Anything beyond Day 30 is treated as later ramp analytics, not the live
onboarding demo.

## Architecture

```text
Streamlit app.py -> guardrails.classify_input
       |                    | on_topic
       |                    v
       |             LangChain/LangGraph agent via ChatOllama
       |                    | 5 tools
       |     search_knowledge_base | get_my_plan / complete_task
       |     Chroma + embeddings   | SQLite via state.py
       |             find_person / escalate_to_hr
       |                    |
       v                    v
guardrails output pass -> streamed answer + Sources
```

`pulse.py` runs beside the chat. The sidebar's simulated date decides when a
weekly check-in is due; the reply is sentiment-scored and stored; the HR view
flags low or declining scores as support signals. HR sees summaries and concern
tags, not private chat transcripts by default.

## Setup

Prerequisites: [Ollama](https://ollama.com) running and
[uv](https://docs.astral.sh/uv/) installed.

```powershell
ollama pull llama3.1:8b
ollama pull qwen2.5:3b-instruct
ollama pull nomic-embed-text

uv sync
uv run python -m stai.ingestion
uv run streamlit run app.py
```

All model names and knobs are env-overridable with `STAI_*`; see
`.env.example`. The guardrail classifier defaults to `qwen2.5:3b-instruct`
because it performed better on the topic battery than the smaller guardrail
option documented in the original plan.

## Demo script

1. Sidebar: sign in as **Alyssa Reyes - Management Trainee / Branch Banking Associate**.
2. Ask: "What do I need to do before my first day?"
3. Ask: "What is my Day 30 Readiness Check?"
4. Ask: "Who do I ask about laptop or system access?"
5. Ask: "Mark MFA setup as done."
6. Ask a payroll or benefits term question to show the first-job decoder.
7. Ask something off-topic to show the input guardrail.
8. Ask something not covered by the handbook to show escalation.
9. Move the simulated date one week forward; AISHA opens with a pulse check-in.
10. Switch to **HR admin** and show support signals, pulse trend, and escalations.

Reset between rehearsals: sidebar -> Demo controls -> Reset demo data.

## Tests

```powershell
uv run pytest
uv run pytest tests/test_pulse.py -k risk
```

Tests are designed to run without Ollama. LLM calls are mocked or injectable.

## Layout

```text
app.py                 Streamlit entry: new-hire chat + HR support dashboard
src/stai/
  config.py            pydantic-settings, env-overridable STAI_* settings
  models.py            Employee, ChecklistItem, PulseResult, GuardrailVerdict
  ingestion.py         hr_docs/*.md -> chunks -> Chroma
  retriever.py         similarity search + metadata filters
  tools.py             five agent tools + RunCapture
  agent.py             ChatOllama agent + AISHA system prompt
  guardrails.py        input classifier, citation enforcement, PII redaction
  pulse.py             check-in scheduling, sentiment scoring, support flag
  state.py             SQLite repo: employees, plans, escalations, pulses
data/
  hr_docs/             fictionalized BDO educational onboarding docs
  org.json             fictional org directory
  employees.json       demo new hires
  plans.json           role ramp templates
docs/BUSINESS_CASE.md  market, wedge, "why not ChatGPT", ROI
tests/                 pytest suite
```

MIT (c) 2026 Mateogas
