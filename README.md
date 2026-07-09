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
[`docs/BUSINESS_CASE.md`](docs/BUSINESS_CASE.md). What was evaluated and what
the experiments found: [`docs/EVALUATION.md`](docs/EVALUATION.md). Architecture
and agentic-flow diagrams: [`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md).

## Project Overview

AISHA demonstrates a complete local-first agentic AI support loop for new-hire
onboarding and early ramp. The prototype combines a conversational UI, RAG,
tool use, persistent state, guardrails, an API endpoint, basic LLMOps logging,
and Docker packaging.

The core demo story is simple: Alyssa should reach her **Day 30 Readiness
Check** with less confusion. AISHA helps by answering from fictionalized
handbook documents, citing sources, reading and updating Alyssa's ramp plan,
routing her to the right human owner, filing People Experience escalations,
and surfacing HR support signals without turning the assistant into
surveillance.

### What it does

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
| Extra | REST API (`/health`, `/chat`) sharing the same guarded pipeline as the UI |
| Extra | Persistent chat memory in SQLite - conversations survive app restarts |
| Extra | Per-turn LLMOps run log (latency, token estimates, tools, sources, errors) |

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

## Architecture Diagram

Rendered diagrams are available in [`docs/assets/`](docs/assets/) and the
editable Mermaid source lives in
[`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md).

![AISHA system architecture](docs/assets/aisha-system-architecture.png)

### Chat Turn Summary

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

## Setup Instructions

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

## REST API

The same guarded agent pipeline is exposed over HTTP, with permissive CORS
enabled so any external site can call it directly, not just server-to-server:

```powershell
uv run uvicorn stai.api:app --reload
```

- `GET /health` - liveness, knowledge-base status, model names.
- `POST /chat` - one agent turn. OpenAPI docs at `http://localhost:8000/docs`.

```powershell
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{
  "employee_id": "emp-alyssa",
  "message": "How do I file a leave request?",
  "sim_date": "2026-07-07"
}'
```

The response carries `answer`, `citations`, `sources`, `escalation_id`,
`plan_changed`, and the input-guardrail `guardrail_category`. If no `history`
is passed, the API uses (and appends to) the persistent chat memory in SQLite,
so API conversations survive restarts.

### Real deployment (LXC on Proxmox, no Docker)

The live deployment is an LXC container with exactly three external port
forwards, so the API and Streamlit each need an explicit, distinct port
rather than relying on defaults:

| External | Internal | Serves |
|---|---|---|
| 2123 | 22 | SSH |
| 2143 | 7860 | REST API |
| 2163 | 8000 | Streamlit |

```powershell
uv run uvicorn stai.api:app --host 0.0.0.0 --port 7860
```

`--host 0.0.0.0` is required - uvicorn's default (`127.0.0.1`) isn't reachable
through the NAT port forward. See `deploy/stai-api.service` for a systemd
unit that keeps this running persistently, matching however the box already
keeps Streamlit alive.

## Observability

Every chat turn - Streamlit or API - appends one JSON line to
`data/observability.jsonl`: route, model names, message/answer sizes, estimated
tokens, latency, tools used, sources retrieved, guardrail category, and errors.
Message *text* is deliberately never logged (support, not surveillance).

```powershell
Get-Content data/observability.jsonl -Tail 5
```

Why a local JSONL log instead of MLflow, and what the fields mean:
[`docs/EVALUATION.md`](docs/EVALUATION.md) and `src/stai/observability.py`.

### Shipping logs to a remote MLflow relay

This box has no spare inbound ports to run an MLflow UI locally, so instead
`src/stai/log_shipper.py` periodically rotates `observability.jsonl` out of
the way and POSTs its records to a relay API on a separate server, which
replays them into a real MLflow backend + UI (see the standalone
`mlflow-relay/` project). One chat turn becomes one MLflow run.

```powershell
# STAI_LOG_SERVER_URL unset (default) => shipping is a no-op
$env:STAI_LOG_SERVER_URL = "http://<relay-host>:8080/log-batch"
$env:STAI_LOG_SHARED_SECRET = "change-me"
uv run python -m stai.log_shipper
```

On the LXC deployment this runs on a timer, not in-process, so shipping
stays alive independent of whether the API/Streamlit services are up: see
`deploy/stai-log-shipper.service` and `deploy/stai-log-shipper.timer`
(`systemctl enable --now stai-log-shipper.timer`).

## Dockerfile / Container Setup

The container holds the app only - Ollama stays on the host (the image makes
no attempt to bundle it):

```powershell
docker build -t aisha-demo .
docker run -p 8501:8501 -e STAI_OLLAMA_BASE_URL=http://host.docker.internal:11434 aisha-demo
```

For the REST API instead of the UI:

```powershell
docker run -p 8000:8000 -e STAI_OLLAMA_BASE_URL=http://host.docker.internal:11434 `
  aisha-demo uv run uvicorn stai.api:app --host 0.0.0.0 --port 8000
```

Prerequisites on the Ollama side: the three models pulled (see Setup). First
run only, build the knowledge base inside the container once Ollama is
reachable:

```powershell
docker exec <container> uv run python -m stai.ingestion
```

On Linux, add `--add-host=host.docker.internal:host-gateway` or point
`STAI_OLLAMA_BASE_URL` at your Ollama container.

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

## Module Ownership Table

Full evidence table, experiments, failure modes, and privacy notes:
[`docs/EVALUATION.md`](docs/EVALUATION.md). Presenter notes and Q&A scripts are
in [`docs/MODULE_PRESENTATION_GUIDE.md`](docs/MODULE_PRESENTATION_GUIDE.md).

Suggested 8-module presentation split, two modules per person:

| Owner | Module | Demo line | Code evidence and inline comments | Tests / proof |
|---|---|---|---|---|
| Person A | Prompt Engineering | AISHA's persona, scope, citation, privacy, and tool rules are injected per turn. | `src/stai/agent.py` (`SYSTEM_PROMPT_TEMPLATE`, `render_system_prompt` docstring); `src/stai/guardrails.py` classifier prompt and few-shot examples. | `tests/test_guardrails.py` |
| Person A | RAG | Ask a handbook question and show `[source: filename.md]` citations plus the Sources expander. | `src/stai/ingestion.py` loads/chunks docs; `src/stai/retriever.py` formats citations; `data/hr_docs/*.md` contains the fictionalized handbook. | `tests/test_ingestion.py`, `tests/test_agent_smoke.py` |
| Person B | Structured Outputs | Pulse and guardrail classifiers return JSON that is parsed into typed models. | `src/stai/models.py` Pydantic models; `src/stai/pulse.py` `parse_pulse`; `src/stai/guardrails.py` `parse_verdict`. | `tests/test_pulse.py`, `tests/test_guardrails.py` |
| Person B | Guardrails | Ask off-topic and prompt-injection questions, then show scoped refusal. | `src/stai/guardrails.py` input classifier, refusals, citation enforcement, and PII redaction comments/docstrings. | `tests/test_guardrails.py` |
| Person C | Disambiguation | Ask AISHA to complete a vague task; it should ask which task instead of guessing. | `src/stai/tools.py` comments around `AMBIGUITY_MARGIN`, `find_task_matches`, and `ambiguous_task_matches`. | `tests/test_disambiguation.py` |
| Person C | Memory | Refresh/switch views after a chat or task update; state persists in SQLite. | `src/stai/state.py` `chat_messages` table and repo methods; `app.py` history loading; `src/stai/api.py` persisted API history comments. | `tests/test_memory.py` |
| Person D | ReAct Agent | Ask for plan, owner lookup, task completion, and escalation in sequence. | `src/stai/agent.py` `create_agent` / `create_react_agent`; `src/stai/tools.py` five tool definitions and `RunCapture`. | `tests/test_agent_smoke.py` |
| Person D | Tool Use | Show local tools: KB search, plan read/update, person lookup, escalation. | `src/stai/tools.py` `search_knowledge_base`, `get_my_plan`, `complete_task`, `find_person`, `escalate_to_hr`. | `tests/test_state_and_tools.py` |

Additional required engineering modules:

| Module | Status | Demo / command | Code evidence and inline comments | Tests / proof |
|---|---|---|---|---|
| Chat UI | Met | `uv run streamlit run app.py`; show Alyssa chat and HR admin dashboard. | `app.py` Streamlit entry point and rendering helpers. | `tests/test_app_boot.py` |
| API Endpoint | Met | `uv run uvicorn stai.api:app --reload`, then open `http://localhost:8000/docs`. | `src/stai/api.py` FastAPI schemas/endpoints; `src/stai/service.py` shared guarded turn pipeline. | `tests/test_api.py` |
| LLMOps Monitoring | Met | `Get-Content data/observability.jsonl -Tail 5` after a chat turn. | `src/stai/observability.py` explains JSONL-over-MLflow rationale and token estimates; `src/stai/log_shipper.py` optional MLflow relay shipping. | `tests/test_observability.py`, `tests/test_log_shipper.py` |
| Dockerization | Met | `docker build -t aisha-demo .`; `docker run -p 8501:8501 -e STAI_OLLAMA_BASE_URL=http://host.docker.internal:11434 aisha-demo`. | `Dockerfile` has inline comments for build/run/API commands and why Ollama stays outside the image; `.dockerignore` keeps the image focused. | Manual build/run documented above |
| SQL Agent | Not claimed | Explain that SQLite is accessed through safe repository methods, not LLM-generated SQL. | `src/stai/state.py` typed SQLite repository methods. | Listed as not met in `ContextKnowledgeBase/ModuleChecklist.md` |

When presenting, be explicit that **SQL Agent is not implemented** and **Tool
Use is local internal tool use**, not a real third-party BDO system integration.

## Layout

```text
app.py                 Streamlit entry: new-hire chat + HR support dashboard
Dockerfile             app container (connects to host Ollama)
deploy/
  stai-api.service          systemd unit for the REST API on the LXC deployment
  stai-log-shipper.service  systemd unit: one shipping pass (see log_shipper.py)
  stai-log-shipper.timer    triggers the above on an interval
src/stai/
  config.py            pydantic-settings, env-overridable STAI_* settings
  models.py            Employee, ChecklistItem, PulseResult, GuardrailVerdict
  ingestion.py         hr_docs/*.md -> chunks -> Chroma
  retriever.py         similarity search + metadata filters
  tools.py             five agent tools + RunCapture + task disambiguation
  agent.py             ChatOllama agent + AISHA system prompt
  guardrails.py        input classifier, citation enforcement, PII redaction
  pulse.py             check-in scheduling, sentiment scoring, support flag
  state.py             SQLite repo: employees, plans, escalations, pulses, chat memory
  service.py           one reusable guarded chat turn (used by the API)
  api.py               FastAPI REST endpoint (/health, /chat)
  observability.py     per-turn JSONL run log (LLMOps)
  log_shipper.py       ships observability.jsonl to a remote MLflow relay
data/
  hr_docs/             fictionalized BDO educational onboarding docs
  org.json             fictional org directory
  employees.json       demo new hires
  plans.json           role ramp templates
docs/BUSINESS_CASE.md  market, wedge, "why not ChatGPT", ROI
docs/EVALUATION.md     module evidence, experiments, failure modes, privacy
tests/                 pytest suite (runs without Ollama)
```

MIT (c) 2026 Mateogas
