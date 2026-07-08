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

## Future changelog rule

When a future chat finishes a task, append a short entry here:

1. Date or commit hash.
2. Files changed.
3. Capability added or decision made.
4. Tests run.
5. Remaining follow-up.
