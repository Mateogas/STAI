# Project Synopsis

## North star

STAI should be presented as an agentic onboarding system that helps companies
catch the invisible failure points of onboarding: confusion, isolation, and
early disengagement.

The product is not just "ChatGPT for HR docs." The stronger thesis is:

> New hires do not quit because they lacked another checklist. They quit
> because small unanswered questions, unclear expectations, and weak social
> connection compound during the first 90 days. STAI gives the employee a safe
> place to ask, gives them concrete next steps, and gives HR an early warning
> while intervention is still possible.

## Current one-liner

STAI is a local-first agentic onboarding assistant that answers policy
questions with citations, manages a new hire's 30-60-90 plan, connects them to
the right people, and flags early attrition risk from weekly pulse check-ins.

## Better presentation angle

Lead with the human use case, then show the architecture.

Suggested framing:

1. A fresh graduate joins a large company.
2. They have practical questions they are embarrassed to ask.
3. They do not know who owns payroll, IT access, benefits, or team norms.
4. A checklist says what to finish, but not how to feel oriented.
5. HR usually discovers struggle too late, often through exit interviews.
6. STAI turns onboarding from a static checklist into an agentic support loop.

## Product pillars

### 1. Safe employee companion

The assistant answers the questions a new hire may feel awkward asking:
payslips, benefits jargon, first-day logistics, policies, workplace acronyms,
and basic "who do I ask?" questions.

Implementation anchors:

- RAG over `data/hr_docs`.
- Citations in `[source: filename.md]` format.
- Judgment-free system prompt.
- Multilingual response instruction.

### 2. Action-oriented onboarding plan

The assistant is not only a Q&A bot. It can read and mutate onboarding state.

Implementation anchors:

- `get_my_plan`
- `complete_task`
- SQLite-backed plan items
- role-specific plan templates in `data/plans.json`

### 3. Connection builder

The assistant routes the employee to the right human instead of saying "ask HR."

Implementation anchors:

- `find_person`
- `data/org.json`
- intro suggestions generated from tool results

### 4. HR early-warning loop

The agent proactively asks check-in questions, scores replies, stores pulse
history, and gives HR a dashboard of risk signals.

Implementation anchors:

- `pulse.py`
- `pulse_checkins` SQLite table
- HR dashboard risk flag
- escalation queue

## Why agentic AI is appropriate

This is a good agentic use case because the app must combine:

- retrieval over unstructured policy documents,
- per-user memory/state,
- tool calls that change onboarding data,
- guardrails for scope and citations,
- proactive check-ins,
- a human-in-the-loop escalation path.

A single prompt would not be enough because the assistant needs to retrieve,
act, remember, and route.

## What the story should avoid

Do not frame this as:

- a generic HR chatbot,
- a policy search box,
- a checklist tracker with an LLM bolted on,
- a "local ChatGPT" demo,
- a developer environment with model names as the main story.

Those are implementation details. The sellable product story is the employee
journey and HR's ability to intervene earlier.

## Pending narrative shift

The next story-spine pass should move from the current Meridian/Maya demo to a
P&G-style enterprise onboarding setting. Keep the technical capabilities, but
ground the narrative in a more recognizable corporate environment:

- large cross-functional organization,
- structured onboarding,
- complex benefits/processes,
- many possible owners for questions,
- HR wants early visibility without turning the experience into surveillance.
