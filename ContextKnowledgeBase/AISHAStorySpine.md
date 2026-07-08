# AISHA Story Spine

This is the source of truth for the narrative rebrand from STAI/Meridian/Maya
to AISHA/BDO/Alyssa. Use this before changing code, data, docs, tests, or UI.

## Locked Decisions

- Product name: AISHA.
- Expansion: AI Support for Hires and Associates.
- Repo/course codename may remain STAI internally, but user-facing narrative
  should present AISHA.
- Business setting: BDO.
- Disclaimer: AISHA is an educational capstone prototype. It is not affiliated
  with, endorsed by, or representative of BDO Unibank. All employee records,
  onboarding documents, org contacts, metrics, and demo interactions are
  fictionalized for storytelling and evaluation purposes.
- Demo employee: Alyssa Reyes.
- Role: Management Trainee / Branch Banking Associate.
- Career stage: fresh graduate or early-career hire.
- Business value: faster productivity and time-to-ramp.
- Secondary value: better belonging, lower manager/HR workload, and earlier
  support before onboarding drag becomes disengagement.
- Core promise: AISHA helps new hires ramp faster without turning support into
  surveillance.

## Story Thesis

Large banks do not lose onboarding time because new hires are incapable of
understanding policies. They lose time because onboarding is fragmented across
systems, people, compliance steps, manager expectations, branch norms, and
support channels.

AISHA closes that support loop. It gives the new hire a safe guide, helps them
find the right owner, tracks role-based ramp progress, watches behavior over
time, and gives managers and HR support signals before small blockers compound.

## What Makes It Agentic

Simple policy Q&A is not enough to justify agentic AI.

AISHA is agentic because it:

- retrieves grounded onboarding and policy context with citations,
- reads and updates the employee's onboarding/ramp state,
- remembers progress across turns,
- routes the employee to the right human owner,
- initiates pulse check-ins,
- compares behavior to role/cohort expectations,
- detects trends over time,
- summarizes support signals for HR without exposing raw private chats,
- keeps a human in the loop for intervention.

## Main Demo Goal

By Day 30, Alyssa should be ready to handle supervised branch customer
interactions with correct process awareness, compliance awareness, and
confidence in who to ask when blocked.

The demo should not frame onboarding as a 90-day checklist. Use:

- Pre-start
- Day 1 Setup
- Week 1 Foundations
- Week 2 Practice and Feedback
- Day 30 Readiness Check

Anything beyond Day 30 is ramp analytics, not "onboarding."

Live demo boundary:

The live demo should stay limited to current or deliberately implemented
prototype capabilities: grounded chat, citations, onboarding/ramp tasks, people
lookup, task updates, pulse check-ins, HR support dashboard, and guardrails.
Future integrations such as HRIS, LMS, calendar, SSO, attendance/absence
patterns, and production access control belong in the expansion/future-work
section only.

## Risk Signals

The killer point is behavior over time, not one emotional message.

Useful fictional signals:

- delayed task completion versus role/cohort baseline,
- repeated questions about the same workflow,
- unresolved access blocker,
- missed manager or buddy touchpoint,
- delayed compliance or branch-shadowing milestone,
- declining pulse score,
- vague or low-confidence pulse replies,
- weak support-network indicators.

Filipino cultural context such as hiya, pakikisama, pakikiramdam, and fear of
being seen as bida-bida can be used carefully as one explanation for why a
capable new hire may hesitate to ask for help. Do not reduce every issue to
"nahihiya."

## Privacy Rule

AISHA is support, not surveillance.

HR should see:

- milestone delays,
- unresolved blockers,
- missed touchpoints,
- pulse trends,
- broad concern tags,
- concise rationale,
- suggested support action.

HR should not see by default:

- full private chat transcripts,
- sensitive personal details,
- raw venting,
- speculative personality judgments,
- punitive labels such as "flight risk" or "poor performer."

Preferred wording:

"AISHA gives HR enough signal to offer help, not enough detail to police the
employee."

## Product Scope

### AISHA Is

- A consultation and support agent for onboarding and early ramp.
- A role-based guide that helps new hires understand next steps, owners, and
  expectations.
- A grounded RAG assistant that answers from fictionalized onboarding/policy
  documents with citations.
- A tool-using agent that can read and update onboarding/ramp state.
- A trend-aware system that can surface delayed milestones, repeated blockers,
  missed touchpoints, and declining pulse signals.
- A manager/HR support aid that suggests humane interventions such as a buddy
  check-in, access unblock, or expectations clarification.

### AISHA Is Not

- A replacement for HR, managers, mentors, or buddies.
- A disciplinary system.
- A surveillance tool.
- A performance rating engine.
- A mental-health diagnosis system.
- A source of official BDO policy or official employee records.
- A guarantee that a new hire will stay, perform, or feel connected.

### Current Prototype Supports

- Local-first Ollama LLMs.
- Chroma RAG over onboarding/HR documents.
- Citations for retrieved sources.
- Guardrails for topic scope, prompt injection, citation enforcement, and PII
  redaction.
- Tool use for plan state, task completion, HR escalation, and people lookup.
- SQLite state for employees, onboarding tasks, escalations, and pulse history.
- Pulse check-ins and trend/risk display.
- Streamlit new-hire chat and HR dashboard.

### Current Prototype Does Not Yet Support

- Real BDO HRIS integration.
- Real employee authentication or SSO.
- Real attendance, sign-in/sign-out, badge, or branch presence data.
- Real calendar or meeting scheduling.
- Real manager/buddy check-in verification.
- Persistent chat history across app restarts unless later implemented.
- Production access control or role-based permissions.
- Full LLMOps/API/Docker claims unless those slices are implemented.

### Expansion Plans

- HRIS integration to sync hires, roles, managers, and onboarding milestones.
- SSO and role-based access control.
- Calendar integration for manager/buddy check-ins.
- Absence-pattern integration as an optional, carefully governed future signal
  for early support, focused on negative trends such as repeated unexplained
  absences rather than hours-at-work monitoring or positive "belonging scores."
- LMS/compliance platform integration for training completion.
- Cohort analytics for role-based task benchmarks.
- More robust privacy controls for what HR can and cannot see.
- Persistent conversation memory with user-controlled visibility.
- Production API, observability, and Docker deployment.

Future absence/attendance boundary:

If attendance-related data is ever integrated, frame it as absence-pattern
awareness for support escalation, not presence tracking. AISHA should not infer
belonging because someone stayed longer in the office, and it should not reward
desk time. A safer future signal is: "Alyssa has multiple unexpected absences
during a delayed ramp period; recommend a supportive check-in," combined with
other onboarding context and strict privacy rules.

## Migration Checklist

When implementation begins, remove or rewrite every visible Meridian/Maya/Meri
reference.

- `app.py`: page title, captions, greeting, assistant name, demo text.
- `src/stai/agent.py`: assistant persona and company context.
- `src/stai/guardrails.py`: company/topic classifier wording.
- `src/stai/pulse.py`: pulse wording and risk language.
- `src/stai/tools.py`: tool descriptions and owner-routing wording.
- `data/employees.json`: replace Maya/Diego/Priya seed personas.
- `data/org.json`: replace Meridian org directory with fictionalized BDO org.
- `data/plans.json`: replace 30-60-90 software/sales/analyst plans with BDO
  onboarding/ramp plans.
- `data/hr_docs/*.md`: replace Meridian handbook docs with fictionalized BDO
  onboarding docs.
- `README.md`: product name, setup narrative, demo script.
- `docs/BUSINESS_CASE.md`: business case, market framing, disclaimer.
- `ContextKnowledgeBase/*.md`: update story, UI brief, project state, module
  checklist where wording references the old narrative.
- `tests/*.py`: update assertions that mention Maya, Meridian, Meri, old roles,
  old plan items, or old org contacts.

Validation command after implementation:

```powershell
rg -n "Meridian|Maya|Meri|Meridian Labs|30-60-90|Software Engineer" .
```

The only acceptable hits after rebrand should be legacy migration notes or
intentional changelog references.
