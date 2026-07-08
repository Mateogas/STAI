# Module Checklist

This file maps the course module checklist to the current codebase.

## Summary

Narrative status:

- Front-facing product is AISHA: AI Support for Hires and Associates.
- Demo setting is fictionalized BDO with the required educational
  disclaimer from `AISHAStorySpine.md`.
- Slice 1 replaced the user-facing seed data, app copy, prompts, handbook docs,
  README, business case, and tests with AISHA/BDO/Alyssa content.
- The main business value is faster productivity/time-to-ramp, supported by
  onboarding/ramp state, trend signals, and HR support cards.

| Module | Current status | Evidence | Next action |
|---|---|---|---|
| Prompt Engineering | Met | Persona system prompt in `agent.py`; few-shot guardrail classifier in `guardrails.py`; guardrail model ablation in `docs/EVALUATION.md`. | Keep. |
| Structured Outputs | Met | Pydantic models parse guardrail and pulse JSON outputs. | Keep. |
| Disambiguation | Met | Deterministic `find_task_matches` + `ambiguous_task_matches` in `tools.py`; `complete_task` refuses ties and lists candidates; `tests/test_disambiguation.py`. | Keep. |
| RAG | Met | `ingestion.py`, `retriever.py`, Chroma, HR docs, source formatting; retrieval examples in `docs/EVALUATION.md`. | Keep. |
| Memory | Met | Streamlit session memory, SQLite domain state, plus persistent `chat_messages` table used by both Streamlit and the API; `tests/test_memory.py`. | Keep. |
| Guardrails | Met | Input topic/injection classifier; citation enforcement; output PII redaction (output-side only, documented). | Keep. |
| ReAct Agent | Met | LangChain/LangGraph agent loop with tools. | Keep. |
| SQL Agent | Not met | SQLite is used through handwritten repository methods; LLM does not generate SQL. | Not claimed; documented in `docs/EVALUATION.md`. |
| Tool Use | Mostly met, caveat | Five internal tools exist. | Internal-tool rationale documented in `docs/EVALUATION.md` (local-first, no real BDO systems). |
| Chat UI | Met | Streamlit chat and HR dashboard in `app.py`. | Redesign flow for usability (Slice 3). |
| API Endpoint | Met | FastAPI `GET /health` + `POST /chat` in `src/stai/api.py`, reusing the pipeline via `src/stai/service.py`; `tests/test_api.py`. | Keep. |
| LLMOps Monitoring | Met | Per-turn JSONL run log in `src/stai/observability.py` (route, models, token estimates, latency, tools, sources, errors); wired into Streamlit and API; `tests/test_observability.py`. | Keep; JSONL-over-MLflow rationale documented. |
| Dockerization | Met | `Dockerfile` + `.dockerignore`; host-Ollama connection and model pulls documented in README. | Verify `docker build` on a machine with Docker. |

## Hard requirements from Specification.pdf

The spec explicitly requires:

- web UI - met (`app.py`),
- REST API endpoint - met (`src/stai/api.py`),
- basic LLMOps monitoring - met (`src/stai/observability.py`),
- Dockerfile - met (`Dockerfile`),
- technical write-up - `docs/EVALUATION.md` + `docs/BUSINESS_CASE.md`,
- experiment findings - `docs/EVALUATION.md` (guardrail ablation, retrieval checks),
- README with setup and architecture - met,
- live demo - script in README; requires Ollama with the three models pulled.

The remaining engineering gap from the spec list is verifying the Docker build
on a machine with Docker installed; everything else has code and tests.

## Defensible current claims

These can be claimed now with code evidence:

- RAG with citations.
- Guardrails.
- Structured outputs.
- ReAct/tool-using agent.
- Streamlit chat UI.
- SQLite-backed onboarding state.
- Pulse/risk dashboard.
- REST API sharing the guarded pipeline.
- Persistent conversation memory (SQLite `chat_messages`, survives restarts).
- Deterministic task disambiguation before mutation.
- Per-turn LLMOps run logging (privacy-preserving: lengths/counts, never text).
- Dockerfile with documented host-Ollama setup.

AISHA-specific claims now supported by Slice 1:

- Role-based onboarding and ramp support for Alyssa Reyes, a fictionalized BDO
  Management Trainee / Branch Banking Associate.
- Day 30 readiness framing instead of the old long-range onboarding story.
- Support-card framing for HR: enough signal to help, not enough detail to
  police.
- Educational/fictional BDO disclaimer throughout demo/docs.

These should be claimed carefully:

- Tool Use: strong internal tool use, but not a third-party external API; the
  local-first rationale is documented in `docs/EVALUATION.md`.
- PII guardrail: output-side redaction only; input text is stored as-is in the
  local SQLite file.
- Token metrics: estimates (~4 chars/token), not exact counts - Ollama via
  LangChain does not reliably report usage.

## Recommended module ownership split

If the team needs module ownership for presentation:

- Person A: RAG, prompt engineering, citations.
- Person B: guardrails, structured outputs, disambiguation.
- Person C: memory, tools, ReAct agent.
- Person D if present: API, Docker, LLMOps, evaluation.

If only three people are presenting, assign API/Docker/LLMOps across the same
people as deployment and reliability responsibilities.
