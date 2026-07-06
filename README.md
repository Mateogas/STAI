# STAI — Onboarding Agent for New Hires

An **agentic AI assistant for new-hire onboarding**, focused on fresh graduates.
Runs **fully local** — Ollama LLMs, Chroma vector store, SQLite state, Streamlit
UI. No data leaves the machine. Built for the fictional company **Meridian
Labs** with a synthetic HR knowledge base.

Why this exists, who pays for it, and how it beats both the incumbents and
"just use ChatGPT": [`docs/BUSINESS_CASE.md`](docs/BUSINESS_CASE.md).

## What it does

| | Feature |
|---|---|
| Baseline | Grounded RAG Q&A over the employee handbook, **with citations** |
| Baseline | Role-personalized **30-60-90 plan** the agent reads and updates via tools |
| Baseline | **Escalation to HR** when the handbook has no answer (ticket queue) |
| Baseline | **HR dashboard**: per-hire progress, pulse trends, risk flags, escalations |
| Differentiator | **First-job decoder** — payslip/benefits-101/jargon docs, judgment-free tone |
| Differentiator | **Proactive pulse check-ins** — agent opens the session weekly, sentiment-scores the reply, flags attrition risk |
| Differentiator | **Connection builder** — org-directory lookup ("who handles payroll?") + intro suggestions |
| Extra | Answers in the user's language; input/output guardrails (topic scope, injection, must-cite, PII redaction) |

## Architecture

```
Streamlit app.py ──► guardrails.classify_input (llama3.2:1b, few-shot)
      │                     │ on_topic
      │                     ▼
      │              LangChain/LangGraph agent (llama3.1:8b via ChatOllama)
      │                     │  5 tools
      │    ┌────────────────┼──────────────────────┐
      │    ▼                ▼                      ▼
      │  search_knowledge_base   get_my_plan / complete_task   find_person / escalate_to_hr
      │  (Chroma + nomic-embed)  (SQLite via state.py)         (org.json / SQLite)
      │                     │
      │                     ▼
      └──── guardrails output pass (must-cite, PII redaction) ──► streamed answer + Sources
```

`pulse.py` runs beside the chat: the sidebar's **simulated date** decides when a
weekly check-in is due; the agent opens with the question; the reply is
sentiment-scored (`PulseResult`) and stored; the HR view flags scores ≤ 2 or
declining trends.

## Setup

Prerequisites: [Ollama](https://ollama.com) running, [uv](https://docs.astral.sh/uv/) installed.

```powershell
ollama pull llama3.1:8b           # agent (tool calling)
ollama pull qwen2.5:3b-instruct   # guardrail + pulse classifier
ollama pull nomic-embed-text      # embeddings

uv sync                           # create venv + install deps
uv run python -m stai.ingestion   # build the Chroma KB (once, ~a minute)
uv run streamlit run app.py
```

All model names and knobs are env-overridable (`STAI_*`, see `.env.example`) —
pointed at whatever hardware the demo runs on. The guardrail classifier ships
as `qwen2.5:3b-instruct` (15/15 on the topic battery; `llama3.2:1b` scored
8/15 and over-blocked benefits questions) — set `STAI_GUARDRAIL_MODEL=llama3.2:1b`
if latency matters more than accuracy on the demo box.

## Demo script (5 minutes)

1. Sidebar: sign in as **Maya Chen — Software Engineer**.
2. *"What do I need to do before my first day?"* → grounded answer, citations, Sources expander.
3. *"Explain my payslip deductions like it's my first job"* → first-job decoder tone.
4. *"Who do I ask about my laptop?"* → Tomas Lindgren (IT) from the org directory + intro suggestion.
5. *"Mark laptop setup as done"* → plan updates, sidebar progress bar moves.
6. *"¿Cuántos días de vacaciones tengo?"* → grounded answer **in Spanish**.
7. *"What's the capital of France?"* → guardrail refusal (never reaches the agent).
8. Ask something the handbook can't answer (e.g. visa sponsorship) → escalation offer → ticket.
9. Sidebar: jump the **simulated date** one week forward → agent opens with a pulse check-in; answer negatively ("honestly I'm overwhelmed…").
10. Switch persona to **HR admin** → risk flag 🚩, pulse trend, the escalation in the queue.

Reset between rehearsals: sidebar → Demo controls → *Reset demo data*.

## Tests

```powershell
uv run pytest                 # 57 tests, no Ollama needed (LLMs mocked)
uv run pytest tests/test_pulse.py -k risk   # single file / pattern
```

Pure-logic tests (guardrail parsing, pulse scheduling/risk math, plan math,
person/task matching, SQLite repo, chunking) plus agent smoke tests on a fake
tool-calling model, plus a headless boot test of the real Streamlit script.

## Layout

```
app.py                 Streamlit entry: new-hire chat + HR dashboard
src/stai/
  config.py            pydantic-settings, everything env-overridable (STAI_*)
  models.py            Employee, ChecklistItem, PulseResult, GuardrailVerdict, …
  ingestion.py         hr_docs/*.md -> chunks -> Chroma (idempotent rebuild)
  retriever.py         similarity search + metadata filters
  tools.py             the 5 agent tools + RunCapture
  agent.py             create_agent(ChatOllama) + persona system prompt
  guardrails.py        input classifier, must-cite check, PII redaction
  pulse.py             check-in scheduling, sentiment scoring, risk flag
  state.py             SQLite repo: employees, plans, escalations, pulses
data/
  hr_docs/             10 synthetic Meridian Labs handbook docs
  org.json             12-person org directory
  employees.json       3 demo new hires        plans.json  role plan templates
docs/BUSINESS_CASE.md  market, wedge, "why not ChatGPT", ROI
tests/                 pytest suite (mocked LLM)
```

MIT © 2026 Mateogas
