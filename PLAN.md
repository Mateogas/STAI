# STAI — HR Onboarding Agent for New Hires (Capstone)

## Context

Capstone/business-case project: an **agentic AI assistant for new-hire onboarding**, focused on fresh graduates. Requirement: must use a VectorDB. Goal: genuinely usable app AND defensible business case. Repo is empty — full greenfield build.

**Stack (decided):** Ollama local LLM, Chroma VectorDB, Streamlit chat UI, synthetic HR docs, LangChain + LangGraph + Pydantic + custom guardrails + RAG. Windows dev machine, uv for packaging.

**Grill-session decisions (locked with user):**
- Graded on **both** live demo and code inspection; deadline soon; demo hardware = cloud machines (specs unknown) → all model names env-configurable.
- **Pulse demo:** sidebar simulated-date picker drives check-in scheduling (no pre-seeded pulse history).
- **Guardrail model:** `llama3.2:1b` few-shot classifier (fast), agent on `llama3.1:8b`; separate `guardrail_model` config field → upgrading guardrail to big model = one env var.
- **State store: SQLite** (stdlib `sqlite3`, small repository layer in `state.py`) — not JSON.
- **Multilingual:** system-prompt line "answer in the user's language" + one rehearsed demo moment. No image input.
- **Auth:** plain persona picker; BUSINESS_CASE states "production sits behind SSO, out of prototype scope."
- **Tests:** thin logic tests + 2–3 agent smoke tests with mocked LLM. Full pyramid rejected (recorded-output churn).
- **Scope: full — nothing cut.** All of A/B/C differentiators + multilingual + date picker ship.

## Business case

Written out in `docs/BUSINESS_CASE.md`, structured as:

**1. Validated market (competitors + who pays):** Enboarder (adaptive 30-60-90 journeys), Leena AI (24/7 HR Q&A bot), BambooHR (checklists/e-sign/packets), Workday (enterprise HCM; bought Paradox for $1B in Oct 2025 → conversational AI onboarding is where the market is going). Companies pay per-seat SaaS. Problem validated.

**2. Baseline — what ALL competitors do (we must match):** task checklists + compliance paperwork, 24/7 grounded Q&A, role-personalized 30-60-90 plans, reminders, HR progress dashboards.

**3. The 10x / underserved wedge:**
- *Distribution:* incumbents need 6–12 week enterprise implementations, per-seat SaaS, cloud data. Ours: local-first (Ollama + Chroma, zero data egress), one-day deploy — serves SMEs and privacy-bound orgs (healthcare, EU/GDPR, finance) the incumbents can't serve cheaply.
- *Product:* incumbents push tasks; none fix why new hires actually quit. ~33% of new hires leave within 90 days; top causes: expectation-reality mismatch (30.3%), no team/culture connection (19.5%), poor onboarding experience (17.4%). Companies with strong onboarding see 82% better retention. Our differentiators each attack a quit-cause (below).

**4. "Why not just ChatGPT?"** — (a) doesn't know company-internal policies → RAG w/ citations; (b) can't receive confidential HR docs → fully local; (c) doesn't know who's asking → per-employee state + role personalization; (d) can't act → tools (checklist updates, escalations, person lookup); (e) can't initiate → proactive pulse check-ins.

## Feature set

### Baseline (competitor parity)
1. **RAG Q&A with citations** over internal HR docs (Chroma).
2. **Role-personalized 30-60-90 plan** — not a flat checklist: tasks grouped into Day-1 / Week-1 / 30 / 60 / 90 phases per role (engineer vs. sales), agent reads/updates via tools, progress bar in UI.
3. **Escalation to HR** — agent files a ticket when KB lacks an answer.
4. **HR dashboard** — separate Streamlit view: per-hire progress, open escalations, pulse/risk flags.

### Differentiators (fresh-grad core)
- **A. First-job decoder (judgment-free)** — extra KB docs: payslip explainer, benefits-101 ("explain like it's my first job — it is"), jargon/acronym glossary. System prompt frames agent as judgment-free: no question too basic, never condescending.
- **B. Proactive pulse + attrition-risk flag** — when a check-in is due (weekly per hire), agent *opens* the session with a check-in question; responses sentiment-scored by LLM classifier (Pydantic `PulseResult`); trend stored; low/declining sentiment → risk flag on HR dashboard. Attacks the 33%/90-day attrition stat directly — the ROI headline.
- **C. Connection builder** — synthetic org directory (`data/org.json`: people, teams, responsibilities); tool `find_person("who handles payroll?")` → name + role + how to reach; agent suggests intro chats from the hire's team/stakeholder map. Attacks 19.5% no-connection quit cause.

## Architecture

```
STAI/
├── app.py                  # Streamlit entry: New Hire chat view + HR Dashboard view
├── pyproject.toml          # uv-managed
├── src/stai/
│   ├── config.py           # pydantic-settings: agent_model, guardrail_model, embed_model,
│   │                       #   paths, pulse cadence — all env-overridable (cloud demo machine)
│   ├── models.py           # Employee, PlanPhase, ChecklistItem, Escalation, Person,
│   │                       #   PulseResult, GroundedAnswer (answer+citations), GuardrailVerdict
│   ├── ingestion.py        # data/hr_docs/*.md → chunk → embed → Chroma (persisted, idempotent)
│   ├── retriever.py        # Chroma retriever, metadata filters (doc_type, department)
│   ├── tools.py            # search_knowledge_base, get_my_plan, complete_task,
│   │                       #   escalate_to_hr, find_person
│   ├── agent.py            # LangGraph create_react_agent + ChatOllama + system prompt
│   ├── guardrails.py       # input: topic/scope+injection classifier → GuardrailVerdict
│   │                       # output: must-cite enforcement, PII regex redaction
│   ├── pulse.py            # check-in scheduling, sentiment classification, risk scoring
│   └── state.py            # SQLite repository: employees, plan progress, escalations, pulse history
├── data/
│   ├── hr_docs/            # synthetic KB (below)
│   ├── org.json            # ~12-person fictional org directory (teams, responsibilities)
│   └── employees.json      # 3–4 fake new hires (role, dept, start date)
├── docs/BUSINESS_CASE.md
└── tests/                  # pytest; pure-logic tests (guardrail parsing, pulse scoring,
                            #   plan-phase math, find_person) + 2–3 agent smoke tests w/ mocked
                            #   LLM (happy path, escalation path) — no Ollama needed in CI
```

**LLM:** `langchain-ollama` `ChatOllama` w/ `llama3.1:8b` for agent (native tool calling), `llama3.2:1b` for guardrail classifier. Embeddings: `nomic-embed-text` via `OllamaEmbeddings`. Fully offline. All three swappable via env vars.

**RAG:** `langchain-chroma`, persisted at `data/chroma/`, `RecursiveCharacterTextSplitter` ~800/100, metadata `source`/`doc_type`/`department`. Run: `python -m stai.ingestion`.

**Agent:** LangGraph prebuilt react agent, 5 tools, system prompt: judgment-free HR onboarding assistant for "Meridian Labs"; always cite; use plan tools for "my tasks"; escalate on KB miss; suggest people via `find_person`.

**Guardrails (custom Pydantic, no guardrails-ai dep):** input classifier on `llama3.2:1b` with ~5 few-shot examples (on-topic / off-topic / injection) — off-topic never reaches agent, back-stopped by agent system prompt; output must-cite check (KB answer w/ zero citations → "not in handbook" + escalation offer); regex PII redaction.

**Pulse flow:** sidebar **simulated-date picker** (demo prop) drives the clock; on session start, `pulse.py` checks if check-in due at simulated date → agent opens with check-in → reply classified (`PulseResult`: sentiment 1–5 + concern tags) → stored → dashboard flags hires w/ score ≤2 or declining trend.

**Multilingual:** system prompt instructs "answer in the language the user writes in"; KB stays English. One rehearsed demo moment. Addresses reviewer's translation sanity-check; multimodal argued irrelevant for text HR Q&A in BUSINESS_CASE.

**UI:** Streamlit sidebar = persona picker (new hire A/B/C or HR admin, no auth — SSO noted as production scope) + simulated-date picker; new-hire view = chat w/ streaming, expandable Sources, plan progress bar; HR view = table of hires (progress %, risk flag, last pulse), escalation queue.

### Synthetic KB (data/hr_docs/)
`pre_employment_requirements.md`, `first_day_guide.md`, `benefits_overview.md`, `benefits_101_explainer.md`, `payslip_explainer.md`, `jargon_glossary.md`, `it_setup.md`, `code_of_conduct.md`, `leave_policy.md`, `office_logistics.md` — fictional "Meridian Labs", cross-referencing so multi-doc retrieval demos well.

## Implementation order

1. Scaffold: `uv init`, deps (`langchain`, `langchain-ollama`, `langchain-chroma`, `langgraph`, `chromadb`, `pydantic`, `pydantic-settings`, `streamlit`, `pytest`), package layout, update `CLAUDE.md` with real commands.
2. `models.py` + `config.py`.
3. Synthetic data: hr_docs, `org.json`, `employees.json`.
4. `ingestion.py` + `retriever.py` → verify retrieval on sample queries.
5. `state.py` + `tools.py` (5 tools).
6. `agent.py`.
7. `guardrails.py`.
8. `pulse.py`.
9. `app.py` (both views).
10. Tests + `docs/BUSINESS_CASE.md`.

## Future work (documented, not built)

- **Agent QA/eval harness:** golden Q&A set graded by LLM-as-judge, retrieval precision checks, red-team injection suite, regression evals on prompt changes.
- Production auth (SSO), real HRIS integration, PDF ingestion.

## Prerequisites (user machine)

- Ollama installed; `ollama pull llama3.1:8b`, `ollama pull llama3.2:1b`, `ollama pull nomic-embed-text`
- `uv` installed (fallback: pip + venv)

## Verification

1. `uv run python -m stai.ingestion` → collection created, doc/chunk count printed.
2. `uv run pytest` → guardrails, pulse scoring, tools, ingestion unit tests pass (mocked LLM).
3. `uv run streamlit run app.py` → live checks:
   - "What are my pre-employment requirements?" → grounded answer + citations.
   - "What do I need to do on my first day?" → differs per selected hire's role.
   - "Explain my payslip deductions" → first-job decoder answer, judgment-free tone.
   - "Who do I ask about my laptop?" → `find_person` returns IT contact from org.json.
   - "Mark laptop setup done" → plan updates, progress bar moves.
   - Jump simulated date forward one week → agent opens with pulse question; negative reply → risk flag appears in HR dashboard.
   - Ask a question in another language (e.g., Spanish/Tagalog) → grounded answer in that language.
   - "What's the capital of France?" → guardrail refusal.
   - Unanswerable KB question → escalation offered, ticket in HR view.
