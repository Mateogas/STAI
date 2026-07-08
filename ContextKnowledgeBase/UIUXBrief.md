# UI/UX Brief

This brief describes what has to change in the user experience. It intentionally
does not prescribe the visual implementation.

## Current UX problem

The current app works, but it feels like a technical demo:

- persona picker is a prototype stand-in but dominates the flow,
- simulated date is exposed as a primary sidebar control,
- suggestion chips are generic demo prompts,
- the new-hire experience is mostly an empty chat,
- the HR dashboard is table-first rather than action-first,
- sources and model/config details make sense to developers but not users,
- the UI does not strongly express the product thesis.

## Desired UX thesis

The product should feel like:

- a new hire's "today in onboarding" cockpit,
- a safe place to ask basic workplace questions,
- a guide that helps the employee find people and finish next steps,
- an HR early-warning console focused on who needs help.

## New-hire view: must change

### 1. Start with the employee journey

The first screen should answer:

- What should I do today?
- What is blocking me?
- Who can help me?
- What can I ask without feeling embarrassed?

### 2. Make the plan visible without making it a laundry list

The 30-60-90 plan should be framed as progress through onboarding phases:

- Day 1
- Week 1
- First 30 days
- First 60 days
- First 90 days

Avoid showing every task as the main visual at all times.

### 3. Make "ask Meri" contextual

Prompt chips should be tied to use cases:

- Benefits and payslip decoder.
- First-day logistics.
- Find the right person.
- Mark a task done.
- I feel stuck/overwhelmed.

### 4. Hide demo controls

The simulated date and persona picker are necessary for the capstone demo, but
they should feel like demo/admin controls, not the product itself.

### 5. Treat citations as trust, not clutter

Sources are important, but they should be shown as evidence/trust affordances.
Do not make the user feel like they are debugging retrieval.

## HR view: must change

### 1. Lead with attention, not tables

The HR admin should first see:

- who is at risk,
- why they are at risk,
- what changed recently,
- what action HR can take.

### 2. Turn pulse data into an action queue

Risk flags should become cards with:

- employee,
- week of onboarding,
- last sentiment,
- trend,
- concern tags,
- suggested next action,
- link to escalation or outreach.

### 3. Keep the table as drill-down

Tables are useful, but they should not be the primary dashboard story.

### 4. Separate escalations from pulse risk

Escalations are explicit help requests.
Pulse risk is inferred early-warning data.
The UI should make that difference clear.

## Demo flow to support

The UI should make this demo feel natural:

1. New hire asks a "basic" question about payslip/benefits.
2. Assistant answers with citations and plain-language tone.
3. New hire asks who handles a concrete issue.
4. Assistant finds a person and suggests an intro.
5. New hire completes a task.
6. A weekly pulse appears.
7. New hire admits feeling overwhelmed.
8. HR view surfaces risk and suggested action.

## Design constraints

- Keep it Streamlit unless a separate decision is made.
- Keep local-first and privacy-friendly positioning.
- Keep citations visible.
- Keep simulated date available for demo.
- Keep HR and new-hire views distinct.
- Do not add authentication beyond the existing persona picker unless needed
  for the assignment.

## What not to optimize first

- Pixel-perfect brand styling.
- Fancy animations.
- More charts.
- More generic dashboard metrics.
- Model configuration UI.

The main UX gap is flow and product framing, not visual decoration.
