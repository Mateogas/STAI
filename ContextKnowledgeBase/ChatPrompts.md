# Chat Prompts

Use these prompts to start focused follow-up chats.

## Generic continuation prompt

```text
We are working in the STAI repo. First read:

1. ContextKnowledgeBase/README.md
2. ContextKnowledgeBase/ProjectSynopsis.md
3. ContextKnowledgeBase/ProjectState.md
4. ContextKnowledgeBase/ImplementationPlan.md
5. ContextKnowledgeBase/ModuleChecklist.md

Then work only on the slice I name below. Do not rediscover the whole repo unless
needed. Keep changes aligned with the local-first HR onboarding assistant thesis.

Slice:
<describe slice here>
```

## API endpoint chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ProjectState.md, ImplementationPlan.md, and ModuleChecklist.md.

Implement Slice 1: REST API endpoint. Add the smallest FastAPI API that exposes
the existing agent through a JSON endpoint while preserving guardrails, tools,
sources, and simulated date behavior. Add focused tests and update README/docs.
Do not redesign the Streamlit UI in this chat.
```

## LLMOps chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ProjectState.md, ImplementationPlan.md, and ModuleChecklist.md.

Implement Slice 2: LLMOps monitoring. Add MLflow or a defensible local
observability layer that logs trace/run metadata, latency, token usage or token
estimates, tool usage, sources, model names, and errors for guardrail, pulse,
and agent calls. Add tests where possible and update README/docs.
```

## Docker chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ProjectState.md, ImplementationPlan.md, and ModuleChecklist.md.

Implement Slice 3: Dockerization. Add a Dockerfile, .dockerignore, and
documented build/run instructions. Keep Ollama external unless there is a very
strong reason not to. Explain how STAI_OLLAMA_BASE_URL should be configured for
host or containerized Ollama.
```

## Memory and disambiguation chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ProjectState.md, ImplementationPlan.md, and ModuleChecklist.md.

Implement Slice 4: persistent chat memory and stronger disambiguation. Add a
SQLite chat_messages table and repo methods, wire Streamlit and the API if
present, and add deterministic clarification behavior before ambiguous task or
person tool actions. Add tests proving persistence and ambiguity handling.
```

## UI/UX design chat

```text
We are working in the STAI repo. Read ContextKnowledgeBase/README.md,
ProjectSynopsis.md, ProjectState.md, ImplementationPlan.md, and UIUXBrief.md.

Do not start by restyling. First produce a concrete UI/UX change plan for the
Streamlit app that turns the current developer demo into a new-hire journey and
an HR action console. Identify what must change, what can stay, and what should
be hidden as demo controls. Then implement only if asked.
```

## P&G story spine chat

```text
We are working on the STAI capstone narrative, not code yet.

Read these files first:
1. ContextKnowledgeBase/README.md
2. ContextKnowledgeBase/ProjectSynopsis.md
3. ContextKnowledgeBase/ProjectState.md
4. ContextKnowledgeBase/ModuleChecklist.md
5. ContextKnowledgeBase/UIUXBrief.md
6. docs/BUSINESS_CASE.md
7. Specification.pdf

Goal: help me rewrite the story spine using a P&G-style onboarding setting
instead of the current Maya/Meridian framing.

Constraints:
- Keep the codebase as-is unless we later decide to rename data.
- Do not pitch this as a generic HR chatbot.
- Anchor the narrative in relatable use cases for a new hire in a large,
  process-heavy company: benefits, payroll, manager/team connection, IT access,
  first-week confusion, and early overwhelm.
- The main demo promise should be: STAI helps HR catch a struggling new hire
  before they quit, while giving the employee a safe place to ask questions.
- Preserve the technical claims: local-first Ollama, Chroma RAG, citations,
  guardrails, tools, memory/state, pulse check-ins, HR dashboard, API/LLMOps/
  Docker as remaining or completed rubric work depending on current state.

Please grill me one question at a time. If the repo can answer a question, read
the repo instead of asking me. For each question, give your recommended answer.

Deliverables:
1. A 30-second pitch.
2. A 2-minute business use-case explanation.
3. A demo storyline in 6-8 beats.
4. A slide outline for the Business Use Case section.
5. A short "why agentic AI" explanation.
6. A list of what wording to remove from the current narrative.
```
