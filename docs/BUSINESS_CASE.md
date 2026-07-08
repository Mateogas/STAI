# STAI — Business Case

> Narrative update pending: the accepted front-facing product/story is now
> AISHA (AI Support for Hires and Associates), using a fictionalized BDO
> educational demo with Alyssa Reyes as the main employee. This business case
> still contains older Meridian/Maya and attrition-first wording until the BDO
> synthetic-data rebrand slice is implemented. See
> `ContextKnowledgeBase/AISHAStorySpine.md`.

**One-liner:** a local-first, agentic onboarding assistant that doesn't just
hand new hires a checklist — it answers the questions they're afraid to ask,
notices when they're about to quit, and tells HR before it happens.

---

## 1. Validated market — someone already pays for this

Employee onboarding software is an established, paid category. Companies pay
per-seat SaaS subscriptions today:

| Player | What they sell | Signal |
|---|---|---|
| **Enboarder** | Adaptive, journey-based onboarding ("30-60-90 journeys", nudges) | Raised $100M+; sells to enterprise HR |
| **Leena AI** | 24/7 conversational HR Q&A bot over company policies | The "ask HR anything" bot, enterprise contracts |
| **BambooHR** | Onboarding checklists, e-signatures, new-hire packets | SME standard; onboarding is a core paid module |
| **Workday** | Enterprise HCM suite with onboarding flows | **Bought Paradox (conversational AI recruiting/onboarding) for ~$1B in Oct 2025** |

The Workday–Paradox acquisition is the clearest possible market signal:
the biggest HCM vendor paid a billion dollars because **conversational AI is
where onboarding is going**. The problem is validated; the budget line exists;
the question is only which wedge a new entrant can win.

## 2. Baseline — what every competitor does (and we must match)

Table stakes across Enboarder/Leena/Bamboo/Workday, all present in STAI:

1. **Task checklists & compliance paperwork** → role-based 30-60-90 plans with
   phase grouping and progress tracking (not a flat list).
2. **24/7 grounded Q&A** → RAG over the employee handbook **with citations**,
   so answers are auditable, not vibes.
3. **Role personalization** → engineer / sales / analyst plans differ; the
   agent knows who's asking (name, role, week of onboarding).
4. **Reminders / follow-ups** → proactive weekly check-ins (below, we go
   further than reminders).
5. **HR visibility** → dashboard: per-hire progress, open escalations, pulse
   trend, risk flags.

## 3. The wedge — where incumbents can't or won't go

### 3a. Distribution wedge: local-first

Incumbents are cloud SaaS with 6–12-week enterprise implementations, per-seat
pricing, and your HR data on their servers. That model **structurally excludes**
two big segments:

- **SMEs** that can't justify implementation projects or enterprise minimums.
- **Privacy-bound organizations** — healthcare, finance, public sector,
  EU/GDPR-conscious companies — for whom "upload employee HR data to a US
  SaaS" is a compliance project or a hard no.

STAI runs **entirely on-premise**: Ollama for the LLMs, Chroma for the vector
store, SQLite for state. **Zero data egress. One-day deployment** (pull three
models, ingest the handbook folder, run). The demo you're watching is the
deployment. Incumbents can't serve this cheaply because their architecture,
pricing, and sales motion all assume cloud multi-tenancy.

### 3b. Product wedge: attack why new hires actually quit

Incumbents push tasks. None of them address the reasons new hires leave —
and **~33% of new hires quit within their first 90 days**. Top causes from
exit surveys:

| Quit cause | Share | STAI differentiator that attacks it |
|---|---|---|
| Expectation–reality mismatch | **30.3%** | **B. Pulse check-ins** surface the mismatch in week 1–2, while it's fixable — not in the exit interview |
| No connection to team/culture | **19.5%** | **C. Connection builder** — org-directory lookups, "who handles X", concrete intro suggestions from day one |
| Poor onboarding experience | **17.4%** | **A. First-job decoder** — payslip explainer, benefits-101, jargon glossary, judgment-free tone; plus grounded answers instead of "ask around" |

Companies with a strong onboarding program see **~82% better new-hire
retention**. That's the ROI headline: replacing one departed new hire is
commonly estimated at 50–100%+ of annual salary (recruiting, ramp time, lost
productivity). **If STAI saves one fresh-grad departure per year, it has paid
for itself many times over** — and it produces the early-warning data
(pulse trend, risk flags) to prove it's doing so.

### The fresh-graduate focus

Every differentiator is tuned for people in their **first job ever**:

- **A. First-job decoder.** Nobody teaches payslips, deductibles, or 401(k)
  matching in school, and juniors are embarrassed to ask. The KB includes
  explainers written for exactly that ("explain it like it's my first job —
  it is"), and the agent's system prompt hard-codes a judgment-free framing:
  no question too basic, never condescending.
- **B. Proactive pulse + attrition risk.** The agent *opens* the conversation
  when a weekly check-in is due. Replies are sentiment-scored (1–5 + concern
  tags) by a local classifier; scores ≤ 2 or a declining trend raise a flag on
  the HR dashboard. HR sees "Maya, week 2, declining, concerns: workload,
  connection" — actionable while the hire is still on board.
- **C. Connection builder.** "Who do I ask about my laptop?" returns a real
  person with role, team, and how to reach them — plus a nudge to book a
  15-minute intro. Connection is the second-biggest quit cause; the agent
  manufactures connections instead of waiting for them to happen.

## 4. "Why not just ChatGPT?"

The default objection to any internal assistant. Five structural answers:

| ChatGPT | STAI |
|---|---|
| (a) Doesn't know company-internal policy — it will guess | RAG over the actual handbook, **citations required** by an output guardrail; a KB miss produces "not in the handbook" + escalation, never a guess |
| (b) Can't be given confidential HR documents (cloud processing) | **Fully local**; the handbook, org data, and every pulse answer stay on company hardware |
| (c) Doesn't know who's asking | Per-employee state: role, department, start date, week, personal plan progress, pulse history |
| (d) Can't *act* | Tools: updates the 30-60-90 plan, files HR escalation tickets, looks up real colleagues |
| (e) Can't *initiate* | Proactive: opens the session with the weekly pulse check-in on its own schedule |

## Prototype scope — deliberate cuts, stated up front

- **Auth:** a persona picker stands in for login. Production sits behind the
  company's **SSO**; identity then comes from the session, not a dropdown.
  Out of prototype scope on purpose — it demos nothing.
- **Simulated-date picker:** pulse cadence is weekly; the sidebar date picker
  compresses weeks into seconds for the demo. Production uses the wall clock.
- **Multilingual, not multimodal:** the agent answers in the user's language
  (system-prompt level; the KB stays English). Image/voice input is argued
  irrelevant for text-based HR Q&A — the modality of HR questions is text.
- **Synthetic data:** Meridian Labs (company, handbook, org chart, hires) is
  fictional by design — it lets us demo confidential-looking flows publicly.

## Future work (documented, not built)

- **Agent QA / eval harness:** golden Q&A set graded by LLM-as-judge,
  retrieval precision checks, a red-team prompt-injection suite, regression
  evals run on every prompt change. This is the first post-prototype
  engineering investment, because agent changes currently regress silently.
- **HRIS integration:** sync hires/plans from BambooHR/Workday instead of
  `employees.json`; write pulse flags back.
- **PDF/Docx ingestion** for real handbooks (the pipeline only assumes
  markdown today).
- **SSO** (OIDC/SAML) and role-based access for the HR dashboard.
- **Guardrail hardening:** the input classifier is a small (3B) few-shot
  model picked by measured accuracy on a topic battery (15/15 vs 8/15 for the
  1B alternative); the model is a one-env-var swap (`STAI_GUARDRAIL_MODEL`)
  either direction — smaller for latency, larger for stricter filtering.

## Why these technology choices

- **Ollama (local LLMs):** the distribution wedge *is* privacy; a cloud LLM
  would delete section 3a. Also: zero per-token cost at SME scale.
- **Chroma (VectorDB):** grounded Q&A over a private handbook is the core
  loop; a persisted local vector store with metadata filtering fits the
  local-first constraint. (Also a hard course requirement — satisfied by an
  architecturally necessary component, not a bolt-on.)
- **LangChain + LangGraph:** native tool-calling agent loop, model-agnostic —
  the same code runs any Ollama model, so hardware decides model size.
- **Pydantic everywhere:** typed domain models, validated LLM classifier
  outputs (`PulseResult`, `GuardrailVerdict`), env-driven config.
- **SQLite:** transactional per-employee state (plans, escalations, pulses)
  with zero infrastructure — matches one-day deploy.
- **Streamlit:** two polished views (chat + dashboard) in one Python file
  each; the UI is not the product, the agent is.
