# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this is

STAI is the repo/course codename for AISHA: AI Support for Hires and
Associates. AISHA is a local-first agentic onboarding and ramp-support
assistant for a fictionalized BDO educational demo. Ollama LLMs + Chroma RAG +
LangChain/LangGraph agent + SQLite state + Streamlit UI all run offline.

Product/market rationale lives in `docs/BUSINESS_CASE.md`; the original build
plan in `PLAN.md`; user-facing setup in `README.md`.

## Context handoff

For continuation work, start with:

1. `ContextKnowledgeBase/README.md`
2. `ContextKnowledgeBase/ContextCatalog.md`
3. `ContextKnowledgeBase/AISHAStorySpine.md`

Then read only the route-specific files listed in `ContextCatalog.md`.

That folder is now the current handoff source of truth:

- `ContextCatalog.md` routes agents to the smallest needed context pack.
- `AISHAStorySpine.md` locks the BDO/AISHA narrative, disclaimer, scope, and
  migration checklist.
- `ProjectSynopsis.md` explains the north star and story direction.
- `ProjectState.md` records what is implemented and missing.
- `ImplementationPlan.md` slices remaining work into separate chats.
- `ModuleChecklist.md` maps the course rubric to the codebase.
- `UIUXBrief.md` records what must change in the UI/UX.

`ContextTransfer.md` is legacy and should be removed after the knowledge base
is reviewed. Do not use it as current context unless auditing the migration.

Current narrative direction:

- Fully rebrand the user-facing demo from Meridian/Maya/Meri to
  BDO/AISHA/Alyssa after the story spine is finalized.
- BDO use is educational and fictionalized only; do not imply affiliation,
  endorsement, real BDO employee data, or access to internal BDO systems.
- Primary value is faster productivity/time-to-ramp, not generic HR Q&A.
- AISHA is support, not surveillance; HR should see support signals, not raw
  private chat transcripts by default.

## Commands

```powershell
uv sync                                  # install (Python 3.12 pinned)
uv run python -m stai.ingestion          # (re)build Chroma KB from data/hr_docs (needs Ollama)
uv run streamlit run app.py              # run the app
uv run pytest                            # full suite - no Ollama needed (LLMs mocked)
uv run pytest tests/test_pulse.py -k risk   # single file / keyword
```

Runtime prerequisites (demo only, not tests): Ollama running with
`llama3.1:8b`, `qwen2.5:3b-instruct`, `nomic-embed-text` pulled.
(PLAN.md specified `llama3.2:1b` for the guardrail; it scored 8/15 on the
topic battery vs qwen's 15/15, so the default moved. The 1b remains one env
var away, which is the upgrade path the plan designed.)

## Architecture

Chat turn pipeline, wired in `app.py`:

`guardrails.classify_input` (small LLM, few-shot; fail-open) ->
`agent.build_agent` (LangChain 1.x `create_agent` + `ChatOllama`, rebuilt every
turn so the system prompt carries persona + simulated date) -> tools mutate
state and record into a `tools.RunCapture` -> `guardrails.apply_output_guardrails`
(must-cite check + PII redaction) rewrites the streamed text before it is
persisted.

Key cross-file contracts:

- `tools.build_tools(employee, repo, sim_date) -> (tools, RunCapture)`:
  tools are closures over the current persona. `RunCapture` is how the UI gets
  the Sources expander and how the must-cite guardrail knows whether
  `search_knowledge_base` ran and what it retrieved.
- Citation format is `[source: <filename>]`, produced by `retriever.format_docs`,
  demanded by the system prompt in `agent.py`, and parsed/enforced by
  `guardrails.enforce_citations`. Change it in all three.
- The clock is the simulated date from the sidebar (`app.py`), threaded into
  pulse scheduling and the system prompt. Never use `date.today()` in
  agent/pulse logic.
- LLM-output parsing is separated from LLM calls (`parse_verdict`,
  `parse_pulse`) so logic tests never need Ollama; classifier LLMs are
  injectable (`llm=` param) and tests pass fakes.
- State goes through `state.Repo` (SQLite, connection-per-op for Streamlit
  threads). Seeded once from `data/*.json`; delete `data/stai.db` to reset the
  demo (or sidebar -> Demo controls).

All config is `pydantic-settings` (`src/stai/config.py`), env-overridable with
prefix `STAI_` (see `.env.example`), especially model names because demo
hardware is unknown.

## Gotchas

- Repo lives under OneDrive: `[tool.uv] link-mode = "copy"` in `pyproject.toml`
  is required (hardlinks fail, os error 396). Transient "Access is denied" on
  `.venv` during installs = OneDrive sync lock; retry.
- `python` on PATH is 3.14; the project pins 3.12 via `.python-version`.
  Always go through `uv run`.
- Ingestion is a full reset-and-rebuild (`reset_collection`), cheap and
  idempotent. Run it after editing anything in `data/hr_docs/`.
- Tests assert against the real `data/*.json` seed data; renaming people/tasks
  will require updating tests.
- `tests/test_app_boot.py` executes `app.py` headlessly via Streamlit
  `AppTest`; it creates/seeds the real `data/stai.db` but never calls an LLM.
