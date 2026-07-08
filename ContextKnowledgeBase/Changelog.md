# Changelog

This file summarizes the inherited git history and the current documentation
reorganization.

## Git history

### `9036a91` - Initial commit

Added repository scaffolding:

- `.gitattributes`
- `.gitignore`
- `LICENSE`

### `fdf0d57` - Implemented Plan.md

Main implementation commit. Added:

- app entry point: `app.py`
- package config: `pyproject.toml`, `.python-version`, `.env.example`
- core package: `src/stai/*`
- synthetic data: `data/*.json`, `data/hr_docs/*.md`
- docs: `PLAN.md`, `README.md`, `docs/BUSINESS_CASE.md`, `CLAUDE.md`
- tests: `tests/*.py`
- lockfile: `uv.lock`

Major capabilities added:

- Streamlit new-hire chat.
- HR dashboard.
- Chroma RAG ingestion and retrieval.
- LangChain/LangGraph agent.
- five internal tools.
- input/output guardrails.
- pulse check-ins and risk flags.
- SQLite state.
- mocked test suite.

### `8318d59` - test

Added empty `test.txt`.

## Current uncommitted/inherited files

At the time this knowledge base was created, these files were present but not
part of the committed history:

- `AGENTS.md`
- `ContextTransfer.md`
- `Specification.pdf`

They appear to be handoff/spec artifacts rather than implementation changes.

## Documentation reorganization

Created `ContextKnowledgeBase/` as the new handoff source of truth.

Purpose:

- reduce repeated context reconstruction,
- make future chat starts cheap,
- split remaining work into separate context windows,
- mark `ContextTransfer.md` as legacy,
- align `CLAUDE.md` and `AGENTS.md` with the new context flow.

## 2026-07-09 - AISHA/BDO story spine and routing prep

Files changed:

- `ContextKnowledgeBase/AISHAStorySpine.md`
- `ContextKnowledgeBase/ContextCatalog.md`
- `ContextKnowledgeBase/README.md`
- `ContextKnowledgeBase/ProjectSynopsis.md`
- `ContextKnowledgeBase/ProjectState.md`
- `ContextKnowledgeBase/ImplementationPlan.md`
- `ContextKnowledgeBase/ModuleChecklist.md`
- `ContextKnowledgeBase/UIUXBrief.md`
- `ContextKnowledgeBase/ChatPrompts.md`
- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/BUSINESS_CASE.md`

Decision made:

- AISHA is the front-facing product name: AI Support for Hires and Associates.
- BDO is the story setting with an explicit educational/fictional disclaimer.
- Alyssa Reyes is the main demo employee.
- Primary value is faster productivity/time-to-ramp, centered on Day 30
  supervised branch readiness.
- AISHA is support, not surveillance.

Follow-up:

- Implement the BDO synthetic-data rebrand slice.
- Add stale-wording/TDD safeguards.
- Redesign Streamlit around the AISHA onboarding/ramp cockpit and HR support
  cards.

## 2026-07-09 - Slice 1 AISHA/BDO synthetic data rebrand

Files changed:

- `data/employees.json`
- `data/org.json`
- `data/plans.json`
- `data/hr_docs/*.md`
- `app.py`
- `src/stai/agent.py`
- `src/stai/guardrails.py`
- `src/stai/models.py`
- `src/stai/pulse.py`
- `src/stai/tools.py`
- `README.md`
- `docs/BUSINESS_CASE.md`
- `tests/*.py`
- `ContextKnowledgeBase/ProjectState.md`
- `ContextKnowledgeBase/ImplementationPlan.md`

Capability added:

- Replaced user-facing demo story with AISHA/BDO/Alyssa.
- Added a stale-wording regression test for user-facing app/source/data/docs.
- Changed plan templates to Pre-start, Day 1 Setup, Week 1 Foundations, Week 2
  Practice and Feedback, and Day 30 Readiness Check.
- Preserved citation format, tool names, `RunCapture`, simulated-date behavior,
  SQLite seed behavior, and mocked/no-Ollama test approach.

Tests run:

- `uv run pytest tests/test_rebrand.py` was attempted but `uv` was not on PATH
  in the current shell.

Remaining follow-up:

- Run full validation once `uv` is available.
- Continue with module checklist gaps: API endpoint, LLMOps, Docker,
  evaluation artifact, persistent memory, and deterministic disambiguation.

## 2026-07-09 - Module checklist close-out: API, LLMOps, Docker, memory, disambiguation, evaluation

Files changed:

- `pyproject.toml` (+ fastapi, uvicorn; dev + httpx)
- `src/stai/service.py` (new: reusable guarded chat turn)
- `src/stai/api.py` (new: FastAPI `GET /health`, `POST /chat`)
- `src/stai/observability.py` (new: per-turn JSONL run log)
- `src/stai/config.py` (`obs_log_path` setting)
- `src/stai/state.py` (`chat_messages` table + add/list/clear methods)
- `src/stai/models.py` (`ChatMessage` model)
- `src/stai/tools.py` (`RunCapture.tool_calls`, `find_task_matches`,
  `ambiguous_task_matches`, `complete_task` ambiguity refusal)
- `app.py` (persistent chat memory load/persist, per-turn observability)
- `Dockerfile`, `.dockerignore` (new)
- `docs/EVALUATION.md` (new)
- `README.md` (API/observability/Docker sections, module ownership table)
- `.env.example`, `.gitignore` (observability log path)
- `tests/test_api.py`, `tests/test_observability.py`, `tests/test_memory.py`,
  `tests/test_disambiguation.py` (new)
- `ContextKnowledgeBase/ProjectState.md`, `ImplementationPlan.md`,
  `ModuleChecklist.md`

Capability added:

- REST API reusing the exact Streamlit pipeline stages, with injectable LLMs
  and TestClient tests (no Ollama).
- LLMOps observability: one JSON line per chat turn (route, models, token
  estimates, latency, tools, sources, errors); JSONL chosen over MLflow for
  the local-first demo, rationale documented; message text never logged.
- Persistent conversation memory in SQLite, used by both Streamlit and the
  API; survives restarts.
- Deterministic task disambiguation: ambiguous references never mutate the
  plan; the agent is handed candidates to ask one clarifying question.
- Docker packaging with documented host-Ollama connection.
- Evaluation/write-up artifact with module evidence, guardrail ablation,
  retrieval checks, failure modes, and privacy notes.

Preserved contracts: citation format `[source: filename.md]`, tool names,
`RunCapture` (extended additively with `tool_calls`), simulated-date behavior,
SQLite seed behavior, AISHA/BDO/Alyssa narrative and disclaimer,
support-not-surveillance boundary, tests runnable without Ollama.

Tests run:

- `uv run pytest`: 86 passed (uv was installed to `~\.local\bin` during this
  session; Python 3.12 provisioned by uv).
- Stale-wording scan over `app.py src data README.md docs tests`: zero
  matches. Remaining hits live only in `ContextKnowledgeBase` migration
  notes/changelog, which the story spine explicitly allows.

Remaining follow-up:

- Slice 3 UI/UX redesign.

## Future changelog rule

When a future chat finishes a task, append a short entry here:

1. Date or commit hash.
2. Files changed.
3. Capability added or decision made.
4. Tests run.
5. Remaining follow-up.
