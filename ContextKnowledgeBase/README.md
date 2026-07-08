# STAI Context Knowledge Base

This folder is the canonical handoff surface for future chats working on STAI.
Start here before reading the older root-level planning documents.

## Why this exists

The repo has enough moving parts that a new chat should not need to rediscover:

- what the project is trying to prove,
- what is already implemented,
- which rubric gaps are still open,
- which tasks can be split into separate context windows,
- which story and UI changes matter most.

Use this folder as the "instant context pack" for follow-up chats.

## Read order

For any new chat, read these first:

1. `ProjectSynopsis.md` - north star, business framing, and product thesis.
2. `ProjectState.md` - what exists in code and what is missing.
3. `ImplementationPlan.md` - remaining work sliced into separate chats.
4. `ModuleChecklist.md` - rubric mapping and evidence.

Then read the relevant specialist file:

- `UIUXBrief.md` for design/UI work.
- `Changelog.md` for commit history and inherited state.
- `ChatPrompts.md` for copy-paste prompts to start focused chats.
- `OpenQuestions.md` for product decisions that should be grilled.

## Legacy handoff status

`ContextTransfer.md` at the repo root is now legacy. It has been folded into
this folder and should be removed after this knowledge base is reviewed.

Do not treat `ContextTransfer.md` as current source of truth unless you are
auditing the migration itself.

## Current source hierarchy

Primary handoff:

- `ContextKnowledgeBase/*.md`

Authoritative implementation:

- `app.py`
- `src/stai/*.py`
- `tests/*.py`
- `data/*.json`
- `data/hr_docs/*.md`

Course/spec source:

- `Specification.pdf`

Older project artifacts:

- `README.md`
- `PLAN.md`
- `docs/BUSINESS_CASE.md`
- `ContextTransfer.md` (legacy)

## Maintenance rule

When a chat changes code or product direction, update the relevant file here:

- code status changed -> `ProjectState.md`
- remaining task changed -> `ImplementationPlan.md`
- module evidence changed -> `ModuleChecklist.md`
- story/north star changed -> `ProjectSynopsis.md`
- UI scope changed -> `UIUXBrief.md`
- commit or major iteration happened -> `Changelog.md`
