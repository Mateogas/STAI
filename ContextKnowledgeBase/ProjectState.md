# Project State

This is the current implementation state after auditing the repo against
`Specification.pdf`, `README.md`, `PLAN.md`, `docs/BUSINESS_CASE.md`, and the
source code.

## Narrative target vs current implementation

Target narrative:

- Front-facing product: AISHA, AI Support for Hires and Associates.
- Setting: fictionalized BDO educational demo with explicit disclaimer.
- Main employee: Alyssa Reyes, Management Trainee / Branch Banking Associate.
- Main value: faster productivity/time-to-ramp through onboarding and ramp
  support.
- Demo milestone: Day 30 supervised branch readiness.
- HR view: support signals and suggested actions, not surveillance.

Current implementation caveat:

- The code/data still contain Meridian/Maya/Meri and 30-60-90 wording until the
  BDO synthetic-data rebrand slice is implemented.
- Do not treat Meridian/Maya as the target story. Use
  `ContextKnowledgeBase/AISHAStorySpine.md` as the target source of truth.
- After the rebrand, run the stale-wording validation from `AISHAStorySpine.md`.

## Implemented core

### Streamlit app

Entry point: `app.py`

Current views:

- New hire chat view.
- HR admin dashboard.
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

Partial:

- Chat history is not persisted across app restarts.
- There is no `messages` or `conversation_history` table.
- Current chat memory passed to the agent is capped to the last 12 messages.

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
- HR risk flag if latest score is low or declining.

### Tests

Implemented:

- Guardrail parsing and citation tests.
- Pulse scheduling and risk tests.
- State and tool tests.
- Ingestion chunking tests.
- Agent smoke tests with a fake tool-calling model.
- Streamlit boot test.

Current limitation:

- There is no dedicated evaluation report artifact for the presentation's
  "Experiment Findings" section.

## Not implemented

### REST API endpoint

Missing:

- FastAPI/Flask/Uvicorn dependency.
- API app module.
- Request/response schemas.
- Endpoint that invokes the same agent pipeline as Streamlit.
- API tests.

### LLMOps monitoring

Missing:

- MLflow or equivalent observability dependency.
- Trace/run logging.
- Latency logging.
- Token usage logging.
- Error logging.
- UI or documented way to inspect runs.

Important nuance:

- Ollama/LangChain may not expose reliable token usage in every response. If
  exact token counts are not available, log estimated input/output tokens and
  document the limitation.

### Dockerization

Missing:

- Dockerfile.
- .dockerignore.
- Docker build/run instructions.
- Notes for connecting to host Ollama or running Ollama separately.

### Strong disambiguation

Partial only:

- Prompt says to ask at most one clarifying question.
- Fuzzy matching exists for task/person lookup.

Missing:

- Deterministic ambiguity detection when multiple tasks or people match.
- A structured clarification flow before tool calls.
- Tests for ambiguous inputs.

### Persistent conversation memory

Partial only:

- Short-term Streamlit memory exists.
- Long-term domain state exists.

Missing:

- Persistent message table.
- Repo methods for loading/saving chat turns.
- Integration with Streamlit and API.
- Tests for persistence across a repo/app restart.

## Current biggest risk

The codebase already demonstrates many modules, but the course specification
explicitly requires:

- web UI and API endpoint,
- LLMOps monitoring,
- Dockerfile with documented build/run,
- experiment findings,
- clean README and module ownership table.

Those are the highest-value next targets because they map directly to the
submission checklist.
