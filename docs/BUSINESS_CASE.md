# AISHA Business Case

> AISHA is an educational capstone prototype. It is not affiliated with,
> endorsed by, or representative of BDO Unibank. All employee records,
> onboarding documents, org contacts, metrics, and demo interactions are
> fictionalized for storytelling and evaluation purposes.

**AISHA** stands for **AI Support for Hires and Associates**. It is a
local-first agentic onboarding and ramp-support assistant for a fictionalized
BDO educational demo.

## One-liner

AISHA helps new hires become productive faster by closing the support loop:
grounded answers, role-based ramp tasks, people routing, proactive check-ins,
and HR support signals without exposing private chat transcripts by default.

## Why this problem matters

Large banks do not lose onboarding time because new hires cannot read policies.
They lose time because onboarding is fragmented across documents, systems,
people, compliance steps, branch norms, manager expectations, and support
channels.

Alyssa Reyes, the main demo employee, is a Management Trainee / Branch Banking
Associate. Her first meaningful milestone is not a generic long-range checklist;
it is **Day 30 Readiness Check**: being ready for supervised branch customer
interactions with process awareness, compliance awareness, and confidence in who
to ask when blocked.

## Baseline capabilities

AISHA matches expected onboarding-assistant table stakes:

| Capability | AISHA implementation |
|---|---|
| Grounded policy help | Chroma RAG over fictionalized onboarding docs with required `[source: filename]` citations |
| Role-based plan | SQLite-backed onboarding and ramp tasks across Pre-start, Day 1 Setup, Week 1 Foundations, Week 2 Practice and Feedback, and Day 30 Readiness Check |
| Action-taking tools | `get_my_plan`, `complete_task`, `find_person`, `escalate_to_hr`, and `search_knowledge_base` |
| HR visibility | Support dashboard with progress, pulse trends, support signals, and escalation queue |
| Guardrails | Topic classifier, prompt-injection refusal, citation enforcement, and output-side PII redaction |
| Local-first privacy | Ollama, Chroma, SQLite, and Streamlit run offline for the demo |

## Differentiated wedge

### 1. Faster time-to-ramp

AISHA keeps the user focused on what moves readiness forward today: which task
is next, who owns a blocker, which learning module matters, and what Day 30
readiness means for the role.

### 2. First-job decoder

Fresh graduates and early-career hires often hesitate to ask basic questions
about payslips, benefits, acronyms, branch routines, and workplace norms. AISHA
answers plainly and routes to the right owner without shaming the user.

### 3. Support before drag compounds

The useful signal is behavior over time, not one emotional message. AISHA can
surface delayed milestones, unresolved access blockers, missed manager or buddy
touchpoints, repeated workflow questions, and declining pulse scores.

### 4. Support, not surveillance

AISHA gives HR enough signal to offer help, not enough detail to police the
employee. The HR view should show concern tags, concise rationale, and suggested
support actions. It should not show raw private chat transcripts by default.

## Why not just a general chatbot?

| General chatbot limitation | AISHA answer |
|---|---|
| Does not know the fictional company context | RAG over the demo handbook with citations |
| Cannot act on ramp state | Tool calls read and update the employee's plan |
| Does not know who is asking | Employee state includes role, department, start date, manager, buddy, and progress |
| Cannot initiate support | Pulse check-ins open on the simulated schedule |
| May blur privacy boundaries | Output guardrails and HR dashboard design avoid raw private-chat exposure |

## Prototype scope

Implemented:

- Streamlit new-hire chat and HR support dashboard.
- Local Ollama LLMs and local Chroma vector store.
- SQLite state for employees, plan items, escalations, and pulse records.
- Fictionalized BDO educational data for Alyssa and two secondary personas.
- Citation format `[source: filename]`.
- Simulated-date pulse scheduling.

Deliberately not implemented in this slice:

- REST API endpoint.
- LLMOps monitoring.
- Docker packaging.
- SSO or production role-based access.
- HRIS, LMS, calendar, attendance, or branch-system integrations.
- Real BDO data, policies, people, systems, or records.

## ROI story

AISHA's value is measured as faster productivity and reduced ramp drag:

- fewer blocked days waiting for the right owner,
- earlier completion of access and compliance learning tasks,
- clearer manager and buddy touchpoints,
- less repeated HR question load,
- earlier support before small blockers become disengagement.

The demo's main proof point is Alyssa reaching Day 30 with supervised branch
readiness, not HR collecting more private information.

## Technology rationale

- **Ollama** keeps the demo local-first.
- **Chroma** supports grounded retrieval over the fictional handbook.
- **LangChain/LangGraph** provides the tool-calling agent loop.
- **Pydantic** validates settings and domain models.
- **SQLite** gives durable local state with no infrastructure.
- **Streamlit** makes the new-hire and HR support views demoable in one app.
