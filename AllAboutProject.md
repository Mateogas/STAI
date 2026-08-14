# All About AISHA

## Project identity

AISHA—AI Support for Hires and Associates—is a local-first, evidence-grounded onboarding decision-support capstone. It is a fictionalized educational demonstration and is not affiliated with, endorsed by, or representative of BDO Unibank. It contains no real employee data and has no access to BDO systems.

The shipped scenario serves one fictional Hire, Alyssa Reyes, across exactly three onboarding topics:

1. Payroll
2. Resource Access
3. HR Policies

AISHA is deliberately narrower than a general HR chatbot. Its job is to determine which current synthetic handbook rule applies to Alyssa's HR-confirmed situation, show structured evidence for the answer, and choose a safe outcome when the available evidence is insufficient. Its primary value is faster, more trustworthy time-to-ramp. It is support, not surveillance.

## Product promise and boundaries

Every policy turn ends in a typed result:

- **Grounded Answer** when eligible evidence supports every material claim.
- **Clarification Request** when one missing confirmed Hire Attribute can change applicability.
- **Abstention** when the active evidence cannot support a conclusion.
- **Escalation Offer** when eligible policy evidence answers part of the question but leaves a material Evidence Gap that HR can resolve.

An Escalation Offer is not an HR case. Alyssa must first see the sharing notice and explicitly consent. Consent copies the linked Policy Conversation into a child Case Thread and mirrors later parent messages only while that case remains open. HR cannot browse unrelated conversations. A bare request to “ask HR,” an unsupported topic, a handbook omission, or a knowledge-index outage cannot manufacture an escalation.

Policy applicability is based on four HR-confirmed attributes: Role Key, Department Key, Employment Classification, and Work Site. Conversation text never changes this profile. Alyssa can request a one-attribute correction, but only an HR approval creates a versioned Hire Profile revision.

## Main user journeys

### Ask AISHA

Alyssa can create, name, reopen, and delete ordered Policy Conversations. AISHA resolves follow-up context, searches only the relevant onboarding topic, evaluates applicability, validates every claim and citation, and returns one of the typed policy outcomes. Evidence is displayed as policy ID, policy revision, handbook version, page, and artifact identity rather than raw retrieval snippets.

### HR clarification and resolution memory

For a partially answered policy question with a deterministic material Evidence Gap, AISHA can offer a consent-first HR route. Once Alyssa consents, HR and the Hire work in the nested Case Thread. HR resolution records a resolution type and scope, posts a Hire-visible summary, stops parent-message mirroring, and becomes Case Resolution Memory for related follow-ups inside that resolved thread.

Raw HR replies never become organization-wide knowledge. Only a non-case-only Policy Clarification that passes a separate policy-owner review may supplement later handbook-grounded answers. A Case Exception stays in its case, while a Policy Amendment Candidate waits for a new handbook revision.

### Certificate Check

Certificate Check is a separate local workflow for structural completeness. It is not authenticity verification, HR approval, medical assessment, diagnosis, or submission. Alyssa must acknowledge this boundary before file processing.

The workflow accepts one PDF, PNG, or JPEG up to 10 MB; PDFs may contain at most three pages. It performs deterministic type, size, page, structure, and active-content checks, followed by local text extraction or Tesseract OCR and deterministic labelled-field rules. The only persistent history is a safe Validation Result. File bytes, filenames, MIME details, extracted text and values, diagnoses, confidence maps, and raw fingerprints are excluded. Results are private by default and may be explicitly shared with HR, revoked, or deleted. The original document belongs in a separate fictional Official HR Document Route.

### HR User

The HR workspace exposes only consented Case Threads, pending one-attribute change requests, and currently shared safe Validation Results. It has no direct policy-conversation browser and no certificate-content route. HR-only notes remain hidden from the Hire; HR-visible replies and case status are shown in the shared thread.

## Knowledge and decision architecture

The sole policy authority is the deterministic 108-page synthetic AISHA Handbook v1.0 generated from `handbook/source.yaml`. The build produces a PDF, page manifest, immutable page-native RAG records, hashes, and a publication report.

Retrieval combines weighted lexical candidates with Chroma dense candidates. Before evidence can support an answer, the system validates the active handbook build, artifact integrity, authority, topic, revision, and applicability. Activation uses immutable hash-named builds and an atomic SQLite pointer; a failed staging build cannot replace the active index. A structurally valid but wrong-topic answer fails closed before display.

The shared `PolicyTurnEngine` is the main seam for both UI and API turns. It performs bounded context resolution, topic gating, retrieval, applicability checks, candidate composition, schema validation, relevance validation, safe persistence, and escalation eligibility. When the configured Ollama model is reachable, it uses a fresh bounded ReAct agent with schema-validated tools. When it is unavailable, the engine records degraded execution and uses a verified deterministic composer.

## Technology stack

- Python 3.12 with `uv` dependency management.
- Pydantic and Pydantic Settings for typed contracts and `STAI_` configuration.
- LangChain/LangGraph with ChatOllama for the bounded ReAct path.
- Chroma plus deterministic lexical retrieval for hybrid RAG.
- SQLite for normalized local application state.
- Streamlit for the two-role demonstration UI.
- FastAPI for the typed `/api/v1` integration surface.
- PyMuPDF, Pillow, and Tesseract for local certificate processing.
- Nager.Holidays as the only bounded product network integration.
- Local JSONL, a batch shipper, an authenticated relay, and a separate MLflow server for LLMOps metadata.
- Docker for the non-root Linux demonstration image.

## State, privacy, and security model

SQLite stores normalized, versioned product state: Alyssa's confirmed profile, Policy Conversations, safe typed turn context and results, evidence identities, escalation offers, Case Threads and messages, resolution memory and review state, notifications, attribute-change requests, Validation Results, idempotency records, holiday cache, retrieval-build pointers, telemetry shipping state, and reset metadata.

The public API owns conversation history, uses fixed simulated dates, safe success/error envelopes, idempotency keys for side effects, optimistic resource versions, and cursor pagination. Demo role namespaces explain product boundaries but are not production authentication or authorization.

Operational telemetry uses a protected four-stage topology:

`schema-v2 local JSONL -> rotating batch shipper -> authenticated FastAPI relay -> separate MLflow server`

Only closed operational metadata is allowed. Hire identifiers, conversation or policy text, certificate content, OCR data, diagnoses, filenames, fingerprints, raw errors, and reconstructable activity are excluded. Monitoring failure cannot change the user-facing policy outcome.

## Evaluation and acceptance

The frozen Composite Safety Benchmark contains 60 synthetic cases: 40 calibration and 20 locked acceptance cases across policy/applicability, retrieval, dialogue safety, Nager, and certificate privacy. P3 is the selected prompt with Locked CSS `0.987481`, every component at least `0.98`, and zero hard failures. This is deterministic contract evidence, not a live-model accuracy claim.

The integrated acceptance process regenerates and verifies the handbook and benchmark, replays the six-turn payroll regression, scans public schemas and SQLite for privacy regressions, checks documentation and module ownership, runs the main offline suite, performs a live Nager check, and runs the non-root Linux container smoke. The separate relay suite is part of the surrounding canonical verification set. Current machine-specific evidence is recorded in [WhatHasBeenImplementedProjectState.md](WhatHasBeenImplementedProjectState.md); remaining release gates are in [ImplementationPlanToDoLeft.md](ImplementationPlanToDoLeft.md).

## Repository map

- `app.py`: Streamlit UI and user journeys.
- `src/stai/turn_engine.py`: shared policy-turn orchestration seam.
- `src/stai/service.py`: shared application service layer.
- `src/stai/api.py`: typed `/api/v1` surface.
- `src/stai/models.py`, `policy.py`, and `guardrails.py`: domain contracts, applicability, and fail-closed validation.
- `src/stai/handbook.py`, `ingestion.py`, and `retriever.py`: handbook generation and hybrid retrieval.
- `src/stai/state.py`: normalized SQLite repository and migrations.
- `src/stai/cases.py` and `clarifications.py`: consented case workflow and reviewed reuse.
- `src/stai/medical.py`: local certificate checks and safe result lifecycle.
- `src/stai/public_holidays.py`: bounded Nager integration.
- `src/stai/observability.py`, `log_shipper.py`, and `mlflow-relay/`: protected LLMOps path.
- `evaluation/`: benchmark fixtures and acceptance artifacts.
- `tests/`: offline behavior, privacy, persistence, API, UI, and regression evidence.
- `ContextKnowledgeBase/`: canonical narrative, decisions, state, module matrix, and route-specific handoff context.

## Explicit non-claims and limitations

AISHA is not a production HR system, policy authority, document-submission system, medical validator, employee-monitoring system, or replacement for human HR judgment. The synthetic handbook, Hire, conversations, benchmark, and certificates do not represent real BDO policies, people, or performance. Production use would require real identity and RBAC, security and privacy review, retention governance, HR/legal/medical review, user research, model evaluation, operational monitoring, and approved policy ownership.

SQL Agent is intentionally unclaimed. SQLite is deterministic application state; Chroma RAG is the selected retrieval module.

## Canonical follow-up sources

Use `ContextKnowledgeBase/ContextCatalog.md` to select the smallest authoritative context pack. The most important sources are:

- `ContextKnowledgeBase/AISHAStorySpine.md` for narrative and locked boundaries.
- `ContextKnowledgeBase/ProjectState.md` for the canonical implementation state.
- `ContextKnowledgeBase/ModuleChecklist.md` for course-module claims and live gates.
- `README.md` for user setup, API, deployment, and demo commands.
- `docs/TECHNICAL_WRITEUP.md` and `docs/ARCHITECTURE_DIAGRAMS.md` for technical detail.
- `docs/EVALUATION.md` for benchmark, privacy, and acceptance evidence.
