# UI/UX Brief

This brief describes what has to change in the Streamlit experience after the
AISHA/BDO/Alyssa story spine. It intentionally does not prescribe visual
implementation details.

## Current UX Problem

The current app works, but it still feels like a technical demo:

- persona picker is a prototype stand-in but dominates the flow,
- simulated date is exposed as a primary sidebar control,
- suggestion chips are generic demo prompts,
- the new-hire experience is mostly an empty chat,
- the HR dashboard is table-first rather than action-first,
- sources and model/config details make sense to developers but not users,
- the UI does not express the AISHA thesis,
- current copy still reflects the older Meridian/Maya/Meri story until the
  rebrand slice is completed.

## Desired UX Thesis

AISHA should feel like:

- Alyssa's "today in onboarding and ramp" cockpit,
- a safe consultation agent for asking and unblocking,
- a guide that helps the employee find the right human owner,
- a manager/HR support console focused on ramp friction,
- a privacy-conscious support loop, not a surveillance dashboard.

## New-Hire View: Must Change

### 1. Start With Day 30 Readiness

The first screen should answer:

- What should Alyssa do next?
- What is blocking her?
- Who can help?
- What does Day 30 supervised branch readiness require?

### 2. Replace 30-60-90 With Onboarding And Ramp Stages

Do not make "30-60-90 onboarding" the main visual. Use:

- Pre-start
- Day 1 Setup
- Week 1 Foundations
- Week 2 Practice and Feedback
- Day 30 Readiness Check

Anything beyond Day 30 can be shown as ramp analytics, not onboarding.

### 3. Make "Ask AISHA" Contextual

Prompt chips should be tied to the new demo:

- Help me unblock an access issue.
- What does Day 30 readiness mean for my role?
- Who owns this branch operations question?
- Mark a ramp milestone done.
- I feel behind on my onboarding.
- What should I prepare before my manager check-in?

Avoid making payroll/benefits the hero use case. Those can exist, but they
should not imply the employee is incapable of understanding basic information.

### 4. Hide Demo Controls

The simulated date and persona picker are necessary for the capstone demo, but
they should feel like demo/admin controls, not the product itself.

### 5. Treat Citations As Trust, Not Clutter

Sources are important, but they should be shown as evidence/trust affordances.
Do not make the user feel like they are debugging retrieval.

### 6. Include The BDO Educational Disclaimer

The UI or demo surface should make it clear that AISHA is an educational
prototype and all BDO employee data, documents, org contacts, metrics, and
interactions are fictionalized.

## HR View: Must Change

### 1. Lead With Support Cards

The HR/admin view should first show:

- who may need support,
- what behavior-over-time signals changed,
- what milestone is delayed,
- what humane support action is suggested,
- what privacy boundary is being respected.

### 2. Make The Aha Moment A Ramp-Delay Support Card

Example card:

```text
Alyssa Reyes - Branch Banking Associate
Ramp status: Needs support
Signal: Day 1 access setup completed 2.1x slower than cohort baseline;
compliance module overdue by 2 days; no buddy check-in logged this week;
pulse confidence dropped from 4 to 2.
Suggested action: Schedule a 15-minute buddy check-in and clarify Day 30
readiness expectations.
Privacy note: No private chat transcript shown by default.
```

### 3. Keep Tables As Drill-Down

Tables are useful, but they should not be the primary dashboard story.

### 4. Separate Explicit Escalations From Trend Signals

Escalations are explicit help requests.
Ramp-delay support signals are inferred from behavior over time.
The UI should make that difference clear.

### 5. Avoid Surveillance Language

Do not use:

- flight risk,
- poor performer,
- watched,
- monitored,
- productivity score,
- belonging score,
- desk time.

Use:

- support signal,
- ramp friction,
- delayed milestone,
- missed touchpoint,
- suggested support action,
- privacy note.

## Demo Flow To Support

The UI should make this demo feel natural:

1. Show the BDO educational disclaimer.
2. Sign in as Alyssa Reyes, Management Trainee / Branch Banking Associate.
3. Show Alyssa's onboarding/ramp cockpit and Day 30 readiness goal.
4. Alyssa asks a grounded branch/compliance/ramp question and receives
   citations.
5. Alyssa asks who owns a blocker; AISHA finds the right person/team.
6. Alyssa completes or updates a milestone.
7. A weekly pulse appears; Alyssa reports low confidence or feeling behind.
8. HR view surfaces a support card with trend signals and a suggested action,
   with no private transcript shown by default.

## Design Constraints

- Keep it Streamlit unless a separate decision is made.
- Keep local-first and privacy-friendly positioning.
- Keep citations visible.
- Keep simulated date available for demo.
- Keep HR and new-hire views distinct.
- Do not add authentication beyond the existing persona picker unless needed
  for the assignment.
- Do not implement future integrations such as HRIS, LMS, calendar, SSO, or
  absence-pattern data in the live demo unless a later slice explicitly scopes
  them.

## What Not To Optimize First

- Pixel-perfect BDO brand styling.
- Fancy animations.
- More charts.
- More generic dashboard metrics.
- Model configuration UI.
- Attendance or absence integrations.

The main UX gap is product flow and AISHA framing, not decoration.
