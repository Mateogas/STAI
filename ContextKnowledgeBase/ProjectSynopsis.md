# Project Synopsis

## North Star

AISHA should be presented as a local-first agentic onboarding and ramp-support
system for a fictionalized BDO educational demo.

The product is not a generic HR chatbot and not a policy search box. The
stronger thesis is:

> New hires in a large bank do not lose ramp time because they cannot
> understand policies. They lose ramp time because onboarding is fragmented
> across systems, people, compliance steps, manager expectations, branch norms,
> and support channels. AISHA closes that support loop while protecting privacy.

## Current One-Liner

AISHA, AI Support for Hires and Associates, is a local-first agentic onboarding
system that helps new hires ramp faster by combining grounded answers,
role-based onboarding state, people lookup, pulse check-ins, and HR support
signals without turning the experience into surveillance.

## Locked Story Setting

- Product name: AISHA.
- Expansion: AI Support for Hires and Associates.
- Business setting: BDO, used with an explicit educational/fictional disclaimer.
- Demo employee: Alyssa Reyes.
- Role: Management Trainee / Branch Banking Associate.
- Main business value: faster productivity and time-to-ramp.
- Demo milestone: Day 30 supervised branch-readiness check.
- Support boundary: HR gets support signals, not raw private chat transcripts by
  default.

Required disclaimer:

> AISHA is an educational capstone prototype. It is not affiliated with,
> endorsed by, or representative of BDO Unibank. All employee records,
> onboarding documents, org contacts, metrics, and demo interactions are
> fictionalized for storytelling and evaluation purposes.

## Better Presentation Angle

Lead with the ramp problem, then show the agentic architecture.

Suggested framing:

1. Alyssa Reyes joins BDO as a Management Trainee / Branch Banking Associate.
2. She is capable, but onboarding is fragmented across access, compliance,
   branch practice, manager expectations, and support channels.
3. Basic Q&A is not enough because the real issue is coordination over time.
4. AISHA gives Alyssa a safe guide and routes her to the right human owner.
5. AISHA tracks role-based onboarding and ramp milestones toward Day 30
   supervised readiness.
6. AISHA notices behavior-over-time signals such as delayed milestones, missed
   buddy touchpoints, repeated blockers, and declining pulse confidence.
7. HR and managers receive a support card with a suggested humane action, not a
   surveillance feed.

## Product Pillars

### 1. Safe New-Hire Guide

AISHA helps a new hire ask questions, understand next steps, and locate the
right owner without feeling exposed or judged.

Implementation anchors:

- RAG over `data/hr_docs`.
- Citations in `[source: filename.md]` format.
- Judgment-free system prompt.
- Multilingual response instruction.

### 2. Role-Based Onboarding And Ramp State

AISHA is not only Q&A. It reads and mutates onboarding state so progress can be
tracked against role expectations.

Implementation anchors:

- `get_my_plan`
- `complete_task`
- SQLite-backed plan items
- role-specific plan templates in `data/plans.json`

Story framing:

- Use onboarding and ramp milestones, not the old long-range checklist framing.
- Hero milestone: Day 30 supervised branch-readiness check.
- Anything beyond Day 30 is ramp analytics, not onboarding.

### 3. Connection Builder

AISHA routes the employee to the right human instead of saying "ask HR."

Implementation anchors:

- `find_person`
- `data/org.json`
- intro suggestions generated from tool results

### 4. HR And Manager Support Loop

AISHA proactively asks pulse questions, stores trend signals, and gives HR or
managers a support card when small blockers start compounding.

Implementation anchors:

- `pulse.py`
- `pulse_checkins` SQLite table
- HR dashboard risk/support display
- escalation queue

Privacy boundary:

- HR should see milestone delays, unresolved blockers, pulse trends, broad
  concern tags, concise rationale, and suggested support action.
- HR should not see full private chat transcripts by default.

## Why Agentic AI Is Appropriate

This is a good agentic use case because AISHA must combine:

- retrieval over unstructured onboarding and policy documents,
- per-user memory/state,
- tool calls that change onboarding data,
- people lookup and owner routing,
- guardrails for scope, citations, and privacy,
- proactive pulse check-ins,
- behavior-over-time trend detection,
- a human-in-the-loop support path.

A single prompt would not be enough because the assistant needs to retrieve,
act, remember, compare progress over time, and route support.

## What The Story Should Avoid

Do not frame this as:

- a generic HR chatbot,
- a payroll or benefits explainer for people who cannot understand policies,
- a policy search box,
- a checklist tracker with an LLM bolted on,
- a "local ChatGPT" demo,
- a surveillance dashboard,
- an attrition fortune-teller,
- a replacement for HR, managers, buddies, or mentors,
- an official BDO system or a source of real BDO employee data.

Preferred wording:

- "faster time-to-ramp"
- "onboarding and ramp milestones"
- "Day 30 readiness"
- "support card"
- "behavior over time"
- "support signals"
- "enough signal to help, not enough detail to police"
