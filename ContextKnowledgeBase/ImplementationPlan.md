# Implementation Plan

This plan is designed for slicing work across separate chats and context
windows. Use `ContextCatalog.md` to decide which files to read for each slice.

## Recommended Sequence

1. Story spine and routing context - done.
2. Generate fictionalized BDO synthetic data and replace the old demo
   narrative - done (Slice 1).
3. Add TDD safeguards for stale wording, rebrand consistency, and behavior
   contracts - done (rebrand regression test plus per-module suites).
4. Redesign UI/UX around Alyssa's Day 30 readiness journey and HR support
   cards - remaining.
5. Close hard rubric gaps: API, LLMOps, Docker - done (Slices 4-6).
6. Strengthen partial modules: disambiguation and persistent memory - done
   (Slice 7).
7. Produce evaluation/write-up artifacts and final README/spec alignment -
   done (Slice 8).

The rebrand is now large enough that it should be treated as an implementation
slice, not a copy pass. Do not mix unrelated architecture changes into the data
generation/rebrand slice unless tests force a small compatibility fix.

## Slice 0 - AISHA Story Spine And Context Routing

Status: done.

Outputs:

- `ContextKnowledgeBase/AISHAStorySpine.md`
- `ContextKnowledgeBase/ContextCatalog.md`
- Updated `AGENTS.md`, `CLAUDE.md`, and context README routing.

Locked decisions:

- AISHA = AI Support for Hires and Associates.
- BDO is the story setting with a clear educational/fictional disclaimer.
- Alyssa Reyes is the main demo employee.
- Role is Management Trainee / Branch Banking Associate.
- Primary value is faster productivity/time-to-ramp.
- Hero milestone is Day 30 supervised branch readiness.
- AISHA is support, not surveillance.

## Slice 1 - BDO Synthetic Data Generation And Full Rebrand

Status: implemented.

Goal:

- Completely replace visible Meridian/Maya/Meri demo content with
  fictionalized BDO/AISHA/Alyssa content.

Inputs:

- `ContextKnowledgeBase/ContextCatalog.md`
- `ContextKnowledgeBase/AISHAStorySpine.md`
- `ContextKnowledgeBase/ProjectState.md`
- existing `data/*.json`
- existing `data/hr_docs/*.md`
- tests that assert old names, roles, task labels, or org contacts

Scope:

- `data/employees.json`
- `data/org.json`
- `data/plans.json`
- `data/hr_docs/*.md`
- `app.py`
- `src/stai/agent.py`
- `src/stai/guardrails.py`
- `src/stai/pulse.py`
- `src/stai/tools.py`
- `README.md`
- `docs/BUSINESS_CASE.md`
- relevant tests

Synthetic data design:

- Main employee: Alyssa Reyes, Management Trainee / Branch Banking Associate.
- Include at least two secondary personas for HR dashboard contrast, but avoid
  returning to software-engineer-as-main-story.
- Create fictional BDO contacts for HR, payroll, benefits, IT access,
  compliance/LMS, branch manager, onboarding buddy, and branch operations.
- Replace "30-60-90" with onboarding/ramp stages:
  - Pre-start
  - Day 1 Setup
  - Week 1 Foundations
  - Week 2 Practice and Feedback
  - Day 30 Readiness Check
- Include fictional cohort baselines where needed for story/demo support, such
  as expected completion windows for access setup, first compliance module, and
  buddy check-in.
- Keep public BDO references broad and safe. Do not invent official real BDO
  policies, real employees, real internal systems, or confidential procedures.

Definition of done:

- App/demo wording uses AISHA/BDO/Alyssa, not Meridian/Maya/Meri.
- BDO educational disclaimer appears in README/business-case and appropriate UI
  or demo docs.
- Tests pass or are updated to the new synthetic data.
- Running the stale-wording search shows only intentional legacy notes:

```powershell
rg -n "Meridian|Maya|Meri|Meridian Labs|30-60-90|Software Engineer" .
uv run pytest
```

## Slice 2 - TDD Safeguards And Rebrand Regression Tests

Goal:

- Prevent stale narrative, duplicate concepts, or accidental surveillance
  language from creeping back in.

Likely tests:

- Implemented in Slice 1: a test scans user-facing source/data/docs for
  forbidden old wording:
  `Meridian`, `Maya`, `Meri`, `30-60-90`, and old role assumptions, allowing
  only explicit legacy notes if needed.
- Tests proving seed data contains Alyssa and the BDO fictional disclaimer where
  expected.
- Tests around plan/ramp phases so code does not assume only legacy phase
  semantics.
- Tests ensuring HR support summaries do not expose raw private pulse/chat text
  by default.
- Existing guardrail/pulse/state/tool tests updated to new data.

Definition of done:

- Rebrand consistency is enforced by tests.
- Old narrative terms cannot silently reappear in user-facing content.
- Tests still run without Ollama.

## Slice 3 - UI/UX Redesign

Goal:

- Turn the Streamlit UI into AISHA's new-hire ramp cockpit and HR support
  console.

Inputs:

- `ContextKnowledgeBase/AISHAStorySpine.md`
- `ContextKnowledgeBase/UIUXBrief.md`
- `app.py`

New-hire view target:

- First screen answers: What should Alyssa do next? What is blocked? Who can
  help? What is the Day 30 readiness target?
- Show onboarding/ramp stages without a laundry list.
- Prompt chips should match the new story: access blocker, compliance module,
  branch shadowing, who owns this, mark milestone done, I feel behind.
- Keep citations visible as trust evidence.

HR view target:

- Lead with support cards, not tables.
- Show support signals: delayed milestone, repeated blocker, missed buddy or
  manager touchpoint, pulse trend, suggested support action.
- Include privacy copy: "No private chat transcript shown by default."
- Keep tables as drill-down only.

Definition of done:

- UI demonstrates the AISHA story in 6-8 beats.
- Demo controls remain available but secondary.
- HR view feels supportive, not punitive or surveillance-oriented.

## Slice 4 - REST API Endpoint

Status: implemented (`src/stai/api.py`, `src/stai/service.py`,
`tests/test_api.py`; run with `uv run uvicorn stai.api:app --reload`).

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

## Slice 5 - LLMOps Monitoring

Status: implemented (`src/stai/observability.py`,
`tests/test_observability.py`). Deviation from the plan below: a local JSONL
run log was chosen over MLflow - the demo is local-first/offline and the
rubric needs traces/latency/tokens/errors, not experiment tracking; the sink
is isolated in `log_turn` so MLflow remains a one-function swap. Rationale
documented in the module docstring and `docs/EVALUATION.md`.

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
  from text length and document that choice.

## Slice 6 - Dockerization

Status: implemented (`Dockerfile`, `.dockerignore`, README instructions).
Build not yet verified on a machine with Docker installed.

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

## Slice 7 - Disambiguation And Persistent Memory

Status: implemented (`find_task_matches`/`ambiguous_task_matches` in
`tools.py`, `chat_messages` table + repo methods in `state.py`, Streamlit and
API integration; `tests/test_disambiguation.py`, `tests/test_memory.py`).

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

## Slice 8 - Evaluation Artifacts

Status: implemented (`docs/EVALUATION.md`; README module ownership/evidence
table and links).

Goal:

- Satisfy the "Experiment Findings" rubric with evidence, not vibes.

Likely artifacts:

- `docs/EVALUATION.md`
- module ownership table in README
- small table of tests and what reliability risk they cover
- guardrail prompt/model ablation already mentioned in config/docs
- retrieval sample queries and expected sources
- failure modes and mitigations
- AISHA privacy/support-not-surveillance evaluation notes

Definition of done:

- Presentation has a credible experiment slide.
- Write-up has an evaluation section.
- README points to evaluation docs.

## Cross-Slice Rules

- Read `ContextCatalog.md` first and only load route-specific context.
- Keep the simulated date behavior for demos.
- Do not use wall-clock date in pulse/agent logic.
- Keep citation format stable unless changing all citation contracts together.
- Keep local-first positioning.
- Keep tests runnable without Ollama where possible.
- Do not imply AISHA is affiliated with or representative of BDO.
- Do not frame AISHA as surveillance, performance scoring, or an HR replacement.
- Update this folder after each slice.
