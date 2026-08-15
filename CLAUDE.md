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

## Agent skills

### Issue tracker

Issues and Wayfinder decision maps are tracked in GitHub Issues. See
`docs/agents/issue-tracker.md`.

### Domain docs

This is a single-context repository with a root `CONTEXT.md` glossary and
architectural decisions under `docs/adr/`. See `docs/agents/domain.md`.

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
uv run python -m stai.ingestion          # stage, verify, and activate Chroma from handbook/dist
uv run streamlit run app.py              # run the app
uv run uvicorn stai.api:app --reload     # run typed REST API (/api/v1)
uv run pytest                            # full suite; LLM calls are mocked
uv run pytest tests/test_pulse.py -k risk   # single file / keyword
```

Runtime prerequisites (demo only, not tests): Ollama running with
`llama3.1:8b`, `qwen2.5:3b-instruct`, `nomic-embed-text` pulled.
(PLAN.md specified `llama3.2:1b` for the guardrail; it scored 8/15 on the
topic battery vs qwen's 15/15, so the default moved. The 1b remains one env
var away, which is the upgrade path the plan designed.)

## Architecture

Chat turn pipeline, shared by `app.py` and `src/stai/api.py`:

`LocalInputClassifier` (required small Ollama model; fail-closed) ->
`PolicyTurnEngine.handle_turn` -> fresh LangChain `create_agent` ReAct loop ->
read-only `build_policy_tools` operations and `RunCapture` -> typed Agent Plan
plus typed response draft -> deterministic handbook/citation/applicability/
claim/privacy/consent validation -> persistence or a deterministic workflow
command. Supported turns have no keyword-planner or local answer fallback.

Key cross-file contracts:

- `tools.build_policy_tools(profile, repo, records, handbook_index=...) ->
  (tools, RunCapture)`: tools are read-only closures over the confirmed Hire
  Profile. `RunCapture` retains retrieved identities and ephemeral exact page
  contents for validation; snippets are not persisted or exposed publicly.
- Citation identity is `PolicyCitation(policy_id, handbook_version, page_start,
  page_end)`. Agent drafts cite only identities captured in the same run, and
  every `PolicyClaim.text` must be an exact contiguous excerpt from cited
  evidence.
- The clock is the simulated date from the sidebar (`app.py`), threaded into
  pulse scheduling and the system prompt. Never use `date.today()` in
  agent/pulse logic.
- ReAct synthesis is finalized through small typed schemas in `agent.py` so the
  local 8B model does not hand-write one large JSON object. Logic tests inject
  an offline agent runner and classifier; production always requires Ollama.
- State goes through `state.Repo` (SQLite, connection-per-op for Streamlit
  threads). Seeded once from `data/*.json`; delete `data/stai.db` to reset the
  demo (or sidebar -> Demo controls).
- LLMOps uses a protected four-stage path: `observability.py` writes local
  JSONL, `log_shipper.py` batches it, `mlflow-relay/` authenticates and maps it,
  and a separate MLflow server stores runs. Preserve this topology and make
  only additive field changes; never log message text or medical content.

All config is `pydantic-settings` (`src/stai/config.py`), env-overridable with
prefix `STAI_` (see `.env.example`), especially model names because demo
hardware is unknown.

## Gotchas

- Repo lives under OneDrive: `[tool.uv] link-mode = "copy"` in `pyproject.toml`
  is required (hardlinks fail, os error 396). Transient "Access is denied" on
  `.venv` during installs = OneDrive sync lock; retry.
- `python` on PATH is 3.14; the project pins 3.12 via `.python-version`.
  Always go through `uv run`.
- Ingestion builds a hash-named staging collection, verifies it, and atomically
  activates it. Run it after handbook changes or when provisioning a new data
  volume; never point SQLite at a collection manually.
- Production requires `llama3.1:8b`, `qwen2.5:3b-instruct`, and
  `nomic-embed-text`, plus an active Chroma build. `/api/v1/health` returns 503
  until all required dependencies are ready. `STAI_AGENT_ENABLED` was removed;
  there is no supported disabled-agent mode.
- Tests assert against the real `data/*.json` seed data; renaming people/tasks
  will require updating tests.
- `tests/test_app_boot.py` executes `app.py` headlessly via Streamlit
  `AppTest`; it creates/seeds the real `data/stai.db`. LLM calls are mocked, but
  if that database points to an active Chroma build the interaction tests still
  require the configured Ollama embedding endpoint.
