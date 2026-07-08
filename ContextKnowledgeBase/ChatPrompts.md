# Chat Prompts

Use these prompts to start focused follow-up chats. Prefer prompts that route
through `ContextCatalog.md` instead of asking an agent to read every markdown
file.

## Generic Continuation Prompt

```text
We are working in the STAI repo. STAI is the repo codename; the front-facing
product is now AISHA: AI Support for Hires and Associates.

First read:
1. ContextKnowledgeBase/README.md
2. ContextKnowledgeBase/ContextCatalog.md
3. ContextKnowledgeBase/AISHAStorySpine.md

Then use ContextCatalog.md to read only the route-specific context for the
slice below. Do not rediscover the whole repo unless needed.

Slice:
<describe slice here>
```

## BDO Synthetic Data And Rebrand Chat

```text
We are working in the STAI repo. The target product/story is AISHA: AI Support
for Hires and Associates, using a fictionalized BDO educational demo.

First read:
1. ContextKnowledgeBase/README.md
2. ContextKnowledgeBase/ContextCatalog.md
3. ContextKnowledgeBase/AISHAStorySpine.md
4. ContextKnowledgeBase/ImplementationPlan.md
5. ContextKnowledgeBase/ProjectState.md

Then implement Slice 1: BDO synthetic data generation and full rebrand.

Goal:
- Completely replace user-facing Meridian/Maya/Meri demo content with
  BDO/AISHA/Alyssa content.
- Main demo employee: Alyssa Reyes, Management Trainee / Branch Banking
  Associate.
- Reframe plans away from "30-60-90 onboarding" into onboarding and ramp
  stages: Pre-start, Day 1 Setup, Week 1 Foundations, Week 2 Practice and
  Feedback, Day 30 Readiness Check.
- Keep all BDO records, org contacts, documents, metrics, and interactions
  fictionalized and covered by the disclaimer.
- Preserve technical contracts: citation format, tool names, RunCapture,
  simulated date, SQLite seed behavior, and tests without Ollama.

Scope to inspect/update:
- data/employees.json
- data/org.json
- data/plans.json
- data/hr_docs/*.md
- app.py
- src/stai/agent.py
- src/stai/guardrails.py
- src/stai/pulse.py
- src/stai/tools.py
- README.md
- docs/BUSINESS_CASE.md
- relevant tests

Use TDD where practical:
- First identify tests that will fail because of old names/old roles.
- Add or update a stale-wording regression test if appropriate.
- Then update data/code/docs and tests.

Validation:
- Run `rg -n "Meridian|Maya|Meri|Meridian Labs|30-60-90|Software Engineer" .`
  and ensure only intentional legacy notes remain.
- Run `uv run pytest`.

Do not implement API, LLMOps, Docker, SSO, HRIS, LMS, calendar, or attendance
integrations in this chat.
```

## TDD Safeguards Chat

```text
We are working in the STAI repo. First read ContextKnowledgeBase/README.md,
ContextKnowledgeBase/ContextCatalog.md, ContextKnowledgeBase/AISHAStorySpine.md,
ProjectState.md, ModuleChecklist.md, and ImplementationPlan.md.

Implement Slice 2: TDD safeguards and rebrand regression tests. Add tests that
prevent stale Meridian/Maya/Meri/30-60-90 wording from reappearing in
user-facing content, while allowing intentional legacy notes if needed. Add or
update tests for AISHA/BDO/Alyssa seed data, onboarding/ramp stages, and privacy
boundaries around HR support summaries. Keep tests runnable without Ollama.
```

## API Endpoint Chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ContextKnowledgeBase/ContextCatalog.md, ContextKnowledgeBase/AISHAStorySpine.md,
ProjectState.md, ImplementationPlan.md, and ModuleChecklist.md.

Implement the REST API endpoint slice. Add the smallest FastAPI API that
exposes the existing agent through a JSON endpoint while preserving guardrails,
tools, sources, simulated date behavior, and AISHA support-not-surveillance
language. Add focused tests and update README/docs. Do not redesign the
Streamlit UI in this chat.
```

## LLMOps Chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ContextKnowledgeBase/ContextCatalog.md, ContextKnowledgeBase/AISHAStorySpine.md,
ProjectState.md, ImplementationPlan.md, and ModuleChecklist.md.

Implement the LLMOps monitoring slice. Add MLflow or a defensible local
observability layer that logs trace/run metadata, latency, token usage or token
estimates, tool usage, sources, model names, and errors for guardrail, pulse,
and agent calls. Add tests where possible and update README/docs.
```

## Docker Chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ContextKnowledgeBase/ContextCatalog.md, ContextKnowledgeBase/AISHAStorySpine.md,
ProjectState.md, ImplementationPlan.md, and ModuleChecklist.md.

Implement the Dockerization slice. Add a Dockerfile, .dockerignore, and
documented build/run instructions. Keep Ollama external unless there is a very
strong reason not to. Explain how STAI_OLLAMA_BASE_URL should be configured for
host or containerized Ollama.
```

## Memory And Disambiguation Chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ContextKnowledgeBase/ContextCatalog.md, ContextKnowledgeBase/AISHAStorySpine.md,
ProjectState.md, ImplementationPlan.md, and ModuleChecklist.md.

Implement persistent chat memory and stronger disambiguation. Add a SQLite
chat_messages table and repo methods, wire Streamlit and the API if present,
and add deterministic clarification behavior before ambiguous task or person
tool actions. Add tests proving persistence and ambiguity handling. Preserve
AISHA privacy boundaries.
```

## UI/UX Design Chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ContextKnowledgeBase/ContextCatalog.md, ContextKnowledgeBase/AISHAStorySpine.md,
ContextKnowledgeBase/UIUXBrief.md, ProjectState.md, and app.py.

Do not start by restyling. First produce a concrete UI/UX change plan for the
Streamlit app that turns the current developer demo into AISHA's new-hire
readiness cockpit and HR support console. Identify what must change, what can
stay, and what should be hidden as demo controls. Then implement only if asked.
```

## Business Case / Slides Chat

```text
We are working on the AISHA capstone narrative and slides.

Read:
1. ContextKnowledgeBase/README.md
2. ContextKnowledgeBase/ContextCatalog.md
3. ContextKnowledgeBase/AISHAStorySpine.md
4. ContextKnowledgeBase/ProjectSynopsis.md
5. ContextKnowledgeBase/ModuleChecklist.md
6. docs/BUSINESS_CASE.md
7. Specification.pdf

Goal: produce business-use-case and business-value slides around AISHA, a
local-first agentic onboarding and ramp-support system for a fictionalized BDO
educational demo.

Must include:
- BDO educational/fictional disclaimer.
- Alyssa Reyes as the main demo employee.
- Time-to-ramp and Day 30 readiness as the primary value.
- Support-not-surveillance privacy boundary.
- Why agentic AI: RAG + tools + memory/state + pulse + guardrails + HR support
  loop.

Do not revert to Meridian/Maya/Meri, P&G, or 30-60-90 onboarding framing.
```
