# Implementation Plan

This plan is designed for slicing work across separate chats and context
windows.

## Recommended sequence

1. Lock the narrative spine.
2. Close hard rubric gaps: API, LLMOps, Docker.
3. Strengthen partial modules: disambiguation and memory.
4. Produce evaluation/write-up artifacts.
5. Hand UI/UX redesign brief to a design-focused chat.
6. Final README/spec alignment pass.

The story spine should be done first, but only lightly. Do not spend days on
copy before closing the required technical gaps.

## Slice 0 - Story spine and P&G framing

Goal:

- Replace the generic/Meridian pitch with a sharper P&G-style onboarding story.

Inputs:

- `ContextKnowledgeBase/ProjectSynopsis.md`
- `ContextKnowledgeBase/ProjectState.md`
- `docs/BUSINESS_CASE.md`
- `README.md`

Outputs:

- Revised north star.
- Demo narrative.
- Presentation outline.
- Product language for README/write-up.

Definition of done:

- The project can be explained in 30 seconds.
- The demo has one main employee journey and one HR payoff.
- The story explains why agentic behavior is necessary.

## Slice 1 - REST API endpoint

Goal:

- Expose the agent through a REST endpoint while reusing the existing pipeline.

Likely implementation:

- Add FastAPI and Uvicorn dependencies.
- Create `src/stai/api.py`.
- Define request schema:
  - `employee_id`
  - `message`
  - optional `sim_date`
  - optional `history`
- Define response schema:
  - `answer`
  - `sources`
  - `citations`
  - `escalation_id`
  - `plan_changed`
  - `guardrail_category`
- Share logic with Streamlit where reasonable, but do not over-refactor.
- Add tests with FastAPI TestClient and fake LLMs if possible.

Definition of done:

- `uv run uvicorn stai.api:app --reload` serves a health endpoint and chat
  endpoint.
- API can answer a mocked or testable request.
- README documents API run and example request.

Risks:

- Streaming does not need to be implemented for the API. A normal JSON response
  is enough for the rubric.

## Slice 2 - LLMOps monitoring

Goal:

- Log traces, latency, token usage/estimates, and errors using MLflow or a
  similarly defensible observability tool.

Likely implementation:

- Add `mlflow` dependency.
- Create `src/stai/observability.py`.
- Add a small wrapper around guardrail, agent, and pulse calls.
- Log:
  - route/source: Streamlit or API,
  - employee id,
  - model names,
  - prompt/message length,
  - estimated input tokens,
  - estimated output tokens,
  - latency milliseconds,
  - tool usage,
  - sources retrieved,
  - error class/message if any.

Definition of done:

- A local run writes MLflow traces/runs.
- README explains how to launch or inspect MLflow.
- At least one test covers the logging wrapper without needing Ollama.

Important note:

- If exact token usage is unavailable from Ollama/LangChain, estimate tokens
  from text length and document that choice. The rubric asks for token usage
  visibility; approximate is better than absent if disclosed.

## Slice 3 - Dockerization

Goal:

- Package the app with documented build/run instructions.

Likely implementation:

- Add `Dockerfile`.
- Add `.dockerignore`.
- Use Python 3.12 base image.
- Install `uv`.
- Copy project files.
- Run `uv sync --frozen`.
- Expose Streamlit port.
- Document host Ollama configuration:
  - container runs app,
  - Ollama can run on host or another container,
  - set `STAI_OLLAMA_BASE_URL` accordingly.

Definition of done:

- Docker image builds.
- README includes one build command and one run command.
- Instructions mention that models must be pulled and KB ingestion must run.

Risk:

- Bundling Ollama models into the app image is unnecessary and likely too
  heavy. Keep Ollama external.

## Slice 4 - Disambiguation and persistent memory

Goal:

- Turn partial modules into defensible module claims.

Disambiguation implementation:

- Make `match_task` return multiple candidate scores or add a
  `find_task_matches` helper.
- If two or more tasks are close, do not mark a task done.
- Return a clarification response listing candidate task ids/titles.
- Add tests for ambiguous task completion.

Memory implementation:

- Add `chat_messages` table.
- Add repo methods:
  - `add_chat_message`
  - `list_chat_messages`
  - `clear_chat_messages`
- Streamlit loads from repo on first render and persists turns.
- API can optionally persist turns too.
- Add tests proving history survives a new `Repo` instance.

Definition of done:

- The presentation can honestly claim short-term session memory plus persistent
  conversation memory.
- Ambiguous action requests trigger clarification before mutation.

## Slice 5 - Evaluation artifacts

Goal:

- Satisfy the "Experiment Findings" rubric with evidence, not vibes.

Likely artifacts:

- `docs/EVALUATION.md`
- module ownership table in README
- small table of tests and what reliability risk they cover
- guardrail prompt/model ablation already mentioned in config/docs
- retrieval sample queries and expected sources
- failure modes and mitigations

Definition of done:

- Presentation has a credible experiment slide.
- Write-up has an evaluation section.
- README points to evaluation docs.

## Slice 6 - UI/UX redesign brief

Goal:

- Give a design-focused chat a concrete list of what has to change, not a
  vague "make it pretty."

Inputs:

- `ContextKnowledgeBase/UIUXBrief.md`
- current `app.py`
- final story spine from Slice 0

Outputs:

- Redesigned Streamlit flow or implementation plan.
- Clear new-hire journey.
- HR dashboard centered on actions and risk.

## Cross-slice rules

- Keep the simulated date behavior for demos.
- Do not use wall-clock date in pulse/agent logic.
- Keep citation format stable unless changing all citation contracts together.
- Do not remove local-first positioning.
- Keep tests runnable without Ollama where possible.
- Update this folder after each slice.
