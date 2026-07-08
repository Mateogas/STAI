# Context Catalog

Use this file as the first routing layer for future STAI/AISHA chats. It tells
agents what to read for the task at hand so they do not load every markdown file
by default.

## Always Read First

For any non-trivial task, read:

1. `ContextKnowledgeBase/README.md`
2. `ContextKnowledgeBase/ContextCatalog.md`
3. `ContextKnowledgeBase/AISHAStorySpine.md`

Then read only the route-specific files below.

## Route: BDO Synthetic Data Generation

Use when generating or replacing demo data, HR docs, employee personas, org
contacts, task plans, or cohort baselines.

Read:

- `ContextKnowledgeBase/AISHAStorySpine.md`
- `ContextKnowledgeBase/ImplementationPlan.md`
- `ContextKnowledgeBase/ProjectState.md`
- `data/employees.json`
- `data/org.json`
- `data/plans.json`
- `data/hr_docs/*.md`
- relevant tests under `tests/`

Output goal:

- Replace Meridian/Maya/Meri demo content with fictionalized BDO/AISHA/Alyssa
  content.
- Preserve the technical contracts: citations, tool names, seed loading,
  simulated date, tests without Ollama.
- Keep BDO disclaimer language visible in docs and appropriate UI surfaces.

Validation:

```powershell
rg -n "Meridian|Maya|Meri|Meridian Labs|30-60-90|Software Engineer" .
uv run pytest
```

## Route: Test-Driven Design

Use when implementing behavior changes with tests first or improving reliability.

Read:

- `ContextKnowledgeBase/AISHAStorySpine.md`
- `ContextKnowledgeBase/ProjectState.md`
- `ContextKnowledgeBase/ModuleChecklist.md`
- `ContextKnowledgeBase/ImplementationPlan.md`
- target source files and existing tests for the behavior being changed

Priority targets:

- deterministic task/person disambiguation,
- persistent chat memory,
- API endpoint tests,
- observability wrapper tests,
- rebrand regression tests that fail on stale Meridian/Maya wording.

## Route: Module Checklist Implementation

Use when closing course-rubric gaps.

Read:

- `Specification.pdf`
- `ContextKnowledgeBase/ModuleChecklist.md`
- `ContextKnowledgeBase/ProjectState.md`
- `ContextKnowledgeBase/ImplementationPlan.md`
- `ContextKnowledgeBase/AISHAStorySpine.md`

Priority order:

1. BDO/AISHA data rebrand if not done yet.
2. REST API endpoint.
3. LLMOps monitoring.
4. Dockerization.
5. Evaluation/write-up artifact.
6. Persistent memory and deterministic disambiguation.

## Route: UI/UX Redesign

Use when redesigning the Streamlit app flow.

Read:

- `ContextKnowledgeBase/AISHAStorySpine.md`
- `ContextKnowledgeBase/UIUXBrief.md`
- `ContextKnowledgeBase/ProjectState.md`
- `app.py`

Design target:

- New-hire view: Alyssa's Day 30 readiness cockpit.
- HR view: support cards, not surveillance tables.
- Demo controls: still available, but visually secondary.
- Sources: trust affordance, not retrieval debugging.

## Route: Business Case / Slides / Write-up

Use when writing pitch, slides, script, or business-value copy.

Read:

- `ContextKnowledgeBase/AISHAStorySpine.md`
- `ContextKnowledgeBase/ProjectSynopsis.md`
- `ContextKnowledgeBase/ModuleChecklist.md`
- `docs/BUSINESS_CASE.md`
- `Specification.pdf`

Must include:

- BDO educational/fictional disclaimer.
- AISHA name and expansion.
- Faster productivity/time-to-ramp as primary value.
- Support-not-surveillance boundary.
- Why agentic AI: RAG + tools + memory/state + pulse + guardrails + HR support
  loop.

## Route: Architecture / Refactor

Use when changing shared architecture or cross-file contracts.

Read:

- `AGENTS.md`
- `ContextKnowledgeBase/ProjectState.md`
- `ContextKnowledgeBase/ModuleChecklist.md`
- `ContextKnowledgeBase/AISHAStorySpine.md`
- source files touched by the contract

Do not change without updating tests and docs:

- citation format `[source: filename]`,
- simulated date clock behavior,
- tool names and `RunCapture` contract,
- SQLite seed/state shape,
- guardrail parsing contracts.

## Routing Rule

If a task touches multiple routes, read the union of the listed route files. Do
not read every markdown file unless the user asks for a broad audit or the task
requires it.
