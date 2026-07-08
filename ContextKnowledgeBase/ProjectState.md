# Project State

This is the current implementation state after auditing the repo against
`Specification.pdf`, `README.md`, `PLAN.md`, `docs/BUSINESS_CASE.md`, and the
source code.

## Narrative implementation

Target narrative:

- Front-facing product: AISHA, AI Support for Hires and Associates.
- Setting: fictionalized BDO educational demo with explicit disclaimer.
- Main employee: Alyssa Reyes, Management Trainee / Branch Banking Associate.
- Main value: faster productivity/time-to-ramp through onboarding and ramp
  support.
- Demo milestone: Day 30 supervised branch readiness.
- HR view: support signals and suggested actions, not surveillance.

Current implementation:

- Slice 1 has rebranded the user-facing app, seed data, handbook docs, README,
  business case, agent prompt, guardrails, pulse wording, tools, and tests to
  AISHA/BDO/Alyssa.
- Legacy narrative references should remain only in explicit migration notes,
  context-routing prompts, or changelog/history entries.
- Keep using `ContextKnowledgeBase/AISHAStorySpine.md` as the narrative source
  of truth for future implementation work.

## Implemented core

### Streamlit app

Entry point: `app.py`

Current views:

- New hire chat view.
- HR support dashboard.
- Sidebar persona picker.
- Simulated date picker for pulse check-in demos.
- Demo reset control.

Current limitation:

- The UI is functional but feels like a dev/demo surface. It exposes prototype
  controls too prominently and does not guide the user through a use-case
  journey.

### Agent pipeline

Main flow:

1. `guardrails.classify_input`
2. `agent.build_agent`
3. LangChain/LangGraph agent with ChatOllama
4. tools built by `tools.build_tools`
5. `tools.RunCapture`
6. `guardrails.apply_output_guardrails`
7. Streamlit renders answer and sources

Important contract:

- Citation format is `[source: filename.md]`.
- If this format changes, update `retriever.py`, `agent.py`, and `guardrails.py`
  together.

### RAG

Implemented:

- Markdown HR docs in `data/hr_docs`.
- Chroma vector store.
- Ollama embeddings.
- Ingestion through `uv run python -m stai.ingestion`.
- Retrieval formatting with inline citations.

### Tools

Implemented in `src/stai/tools.py`:

- `search_knowledge_base`
- `get_my_plan`
- `complete_task`
- `escalate_to_hr`
- `find_person`

Note:

- The tools are internal application tools. The course checklist's "Tool Use"
  description mentions at least one external tool/API. If the instructor reads
  that strictly, this is a caveat.

### State and memory

Implemented:

- SQLite repository in `src/stai/state.py`.
- Employee seed data.
- Plan items.
- Escalations.
- Pulse check-ins.
- Short-term chat state in Streamlit session state.
- Persistent conversation memory: `chat_messages` table with
  `add_chat_message` / `list_chat_messages` / `clear_chat_messages`.
  Streamlit loads persisted history on first render and persists every turn
  (greeting, check-in questions, user messages, answers with sources,
  refusals). The API loads persisted history when the request has none and
  persists every turn. Covered by `tests/test_memory.py`.

Notes:

- Chat memory passed to the agent is capped to the last 12 messages
  (`service.HISTORY_LIMIT`, mirrored in `app.py`).
- Deleting `data/stai.db` (or sidebar demo reset) clears chat memory with the
  rest of the demo state.

### Guardrails

Implemented:

- Input classifier: on-topic/off-topic/injection.
- Fail-open behavior if classifier fails.
- Output citation enforcement.
- Output-side PII redaction.

Important limitation:

- PII redaction is output-side only. Input-side PII detection is not implemented.

### Pulse and risk

Implemented:

- Weekly check-in scheduling based on simulated date.
- LLM-scored pulse sentiment.
- Concern tags.
- Pulse records stored in SQLite.
- HR support flag if latest score is low or declining.

### Tests

Implemented:

- Guardrail parsing and citation tests.
- Pulse scheduling and risk tests.
- State and tool tests.
- AISHA/BDO stale-wording regression test.
- Ingestion chunking tests.
- Agent smoke tests with a fake tool-calling model.
- Streamlit boot test.

- New test files: `test_api.py`, `test_observability.py`, `test_memory.py`,
  `test_disambiguation.py`.

### REST API endpoint

Implemented in `src/stai/api.py` + `src/stai/service.py`:

- FastAPI + Uvicorn dependencies in `pyproject.toml`.
- `GET /health`: status, KB readiness, employee count, model names, disclaimer.
- `POST /chat`: `employee_id`, `message`, optional `sim_date` and `history`;
  responds with `answer`, `citations`, `sources`, `escalation_id`,
  `plan_changed`, `guardrail_category`, `refused`.
- `service.run_chat_turn` reuses the exact Streamlit pipeline stages:
  `classify_input` -> `build_agent`/`run_agent` -> `apply_output_guardrails`.
- LLMs injectable via FastAPI dependency overrides; `tests/test_api.py` runs
  with fakes, no Ollama.
- Run with `uv run uvicorn stai.api:app --reload`.

### LLMOps monitoring

Implemented in `src/stai/observability.py`:

- One JSON line per chat turn (Streamlit and API) appended to
  `data/observability.jsonl` (`STAI_OBS_LOG_PATH`).
- Fields: route, employee id, model names, message/answer sizes, estimated
  input/output tokens, latency ms, guardrail category, tools used, source
  names, escalation id, plan changed, error class/message.
- Message text is deliberately never logged (support-not-surveillance).
- Token counts are estimates (~4 chars/token) because Ollama via LangChain
  does not reliably report usage; documented in the module and
  `docs/EVALUATION.md`, with the JSONL-over-MLflow rationale.
- `tests/test_observability.py` covers the logger, the timer/error capture,
  and end-to-end logging through `run_chat_turn` with fakes.

### Dockerization

Implemented:

- `Dockerfile` (python:3.12-slim + uv, `uv sync --frozen --no-dev`, Streamlit
  CMD, API run documented) and `.dockerignore`.
- Host Ollama connection via `STAI_OLLAMA_BASE_URL=http://host.docker.internal:11434`
  (Linux note included); the image does not bundle Ollama.
- Build/run commands in README. Not yet verified with an actual `docker build`
  on this machine (no Docker available in the dev environment).

### Disambiguation

Implemented in `src/stai/tools.py`:

- `find_task_matches` returns scored candidates; `ambiguous_task_matches`
  flags two or more open tasks within a 0.1 score margin.
- `complete_task` refuses to mutate on ambiguity and returns an `AMBIGUOUS:`
  message listing candidate ids/titles so the agent asks one clarifying
  question; numeric ids always resolve exactly.
- `find_person` stays read-only and returns up to two candidates - surfacing
  both humans is the routing disambiguation.
- `tests/test_disambiguation.py` covers detection, refusal-before-mutation,
  id resolution, and ambiguity clearing once a candidate is done.

### Evaluation artifact

Implemented: `docs/EVALUATION.md` - module evidence table, guardrail model
ablation, retrieval sanity checks, reliability-risk test map, failure modes,
and privacy evaluation. README links it and carries the module ownership /
evidence table.

## Current biggest risk

The hard spec requirements (web UI, API, LLMOps, Docker, write-up, experiment
findings, README) all have code and tests. Remaining risks:

- The Docker build is documented but not yet executed on a machine with
  Docker.
- The Streamlit UI still reads as a dev surface; the UI/UX redesign
  (Slice 3, `UIUXBrief.md`) is the main remaining polish item.
- Live-demo quality still depends on local Ollama models being pulled and the
  KB ingested.
