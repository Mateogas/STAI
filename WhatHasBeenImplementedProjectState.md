# What Has Been Implemented — Project State

**Snapshot date:** 2026-08-15, Asia/Manila

**Branch before this documentation commit:** `main` at `0595846`

**Overall state:** feature-complete educational capstone; offline verification is green; three environment-dependent live module gates remain.

## Verification performed for this snapshot

| Check | Result |
|---|---|
| Main offline test suite | **Passed:** 142 tests, 6 warnings, 15.39 seconds |
| Separate MLflow relay suite | **Passed:** 6 tests, 1 warning, 6.97 seconds |
| Deterministic handbook gate | **Passed:** 108 pages, handbook v1.0 |
| Frozen benchmark | **Passed:** P3 selected, Locked CSS 0.987481, zero hard failures |
| Six-turn dialogue regression | **Passed:** correct offer-then-consent progression and zero wrong-topic citations |
| Privacy/replacement scan | **Passed:** 28 public OpenAPI paths, 30 SQLite tables, zero legacy regressions |
| Live Nager demonstration | **Passed:** live 2026 result with exact `Based on Nager.` attribution |
| Integrated acceptance | **Partial:** its main-suite and Docker stages were skipped for this run; the suite passed separately, and three module rows remain live-gate pending |

The main shell did not expose `uv` on `PATH`, so the installed project virtual environments were used directly for the two test suites. This is a workstation setup issue, not a test failure.

## Implemented product scope

- One fictional Hire: Alyssa Reyes.
- Exactly three onboarding topics: Payroll, Resource Access, and HR Policies.
- Four HR-confirmed applicability attributes with versioned one-attribute correction requests.
- Four typed policy outcomes plus a separate escalation-confirmation result.
- Visible educational-use and non-affiliation boundaries.
- Support-first privacy model with no default HR access to private Policy Conversations.

## Implemented handbook and retrieval

- Deterministic 108-page AISHA Handbook v1.0 generated from normalized YAML.
- PDF, page manifest, immutable RAG page records, artifact hashes, and publication verification.
- Immutable hash-named Chroma build lifecycle with staging verification, activation, prior-build pointer, and rollback.
- Hybrid weighted lexical and dense retrieval.
- Active-version, integrity, authority, applicability, policy-subject, topic, and claim/citation gates.
- Structured citations containing policy ID, revision, handbook version, page, and artifact identity.
- Safe deterministic lexical composition when the live model/index path is unavailable.

## Implemented orchestration and guardrails

- Shared `PolicyTurnEngine` used by Streamlit and FastAPI.
- Restart-safe follow-up context and server-owned ordered conversation history.
- Bounded ReAct path using a fresh agent and schema-validated read-only tools when Ollama is ready.
- Fail-closed typed parsing and output validation.
- Wrong-topic citation rejection before persistence or display.
- Input classification with safe fail-open behavior; evidence, applicability, consent, escalation, clarification promotion, and certificate privacy fail closed.
- Deterministic Evidence Gap assessment; unsupported topics, omissions, outages, and bare human requests cannot create cases.

## Implemented memory and HR workflow

- Multiple named and reopenable Policy Conversations.
- Evidence-gated Escalation Offers separate from consent.
- Explicit sharing notice before case creation.
- Consented child Case Threads with parent-history backfill and future-message mirroring while open.
- Hire and HR replies, HR-only notes, status, versions, events, notifications, unread state, and resolution.
- Typed Case Resolution Memory for related follow-ups inside resolved threads.
- Separate review flow for reusable Policy Clarifications.
- Case Exceptions constrained to their thread; amendment candidates constrained to future handbook publication.
- No HR product route for unrelated Policy Conversations.

## Implemented Certificate Check

- Acknowledgement before file processing.
- PDF, PNG, and JPEG support with size, page-count, magic-byte, structure, and active-content gates.
- Local PDF text extraction and local Tesseract OCR.
- Deterministic name, date, duration, and labelled-field rules.
- One safe replacement retry and terminal human-review path.
- Result-only persistence with explicit share, revoke, and delete lifecycle.
- Upload rejection and check failure create no Validation Result or fingerprint.
- Installation-local HMAC fingerprint key stored outside SQLite with restrictive permissions and safe key-loss behavior.
- No persisted or public certificate bytes, filename, MIME detail, extracted value, diagnosis, confidence map, or raw fingerprint.

## Implemented UI and API

- Streamlit destinations: Ask AISHA, Certificate Check, History, and HR User.
- Reopenable conversation rail with nested Case Threads, unread counts, text status, sharing banners, and resolved-thread follow-up input.
- Distinct non-color-only outcome presentation, metadata-only evidence, accessible status/live regions, visible focus, 44-pixel targets, and narrow-screen contract tests.
- Typed `/api/v1` only; legacy `/chat` and unversioned `/health` are absent.
- Safe `{data, meta}` and `{error, meta}` envelopes.
- Fixed simulated dates, configured CORS, request IDs, server-owned history, idempotent replay, optimistic versions, and bounded cursor pagination.
- Role-separated demo namespaces and one truthful health endpoint.
- API privacy denylist covering internal retrieval, certificate, model, exception, and persistence details.

## Implemented external tool and LLMOps

- Philippines-only Nager.Holidays lookup for the simulated current/following year.
- Exact attribution, response validation, retry, seven-day cache, circuit breaker, expired fallback, and conflict handling.
- No private product data sent to Nager; Nager availability does not control application health.
- Schema-v2 privacy-safe telemetry.
- Preserved local JSONL -> rotating shipper -> authenticated relay -> separate MLflow topology.
- Allowlists, v1 sanitization, quarantine, bounded retention, partial acknowledgement, retry, event idempotency, fixed experiment routing, and total failure isolation.

## Implemented evaluation and deployment assets

- Frozen 60-case Composite Safety Benchmark with calibration/locked separation and P1/P2/P3 comparison.
- Integrated acceptance orchestrator and versioned acceptance artifacts.
- Six-turn production dialogue regression shared by module tests, API tests, and container smoke.
- Non-root Python 3.12 Dockerfile using UID 10001 with Tesseract English and persistent `/app/data`.
- Container smoke for Streamlit, API, policy dialogue, consent progression, and a synthetic certificate.
- Disposable-staging predeployment dialogue gate that requires live health `ready`.
- Documentation, architecture diagrams, technical write-up, presentation guide, ADRs, and balanced module ownership.

## Current workstation/runtime state

| Runtime dependency | Current state | Consequence |
|---|---|---|
| Project Python virtual environment | Present and working | Offline suite can run |
| `uv` command | Not visible on shell `PATH` | Canonical `uv run ...` commands need PATH/install repair |
| Ollama executable | Installed | Runtime is available in principle |
| Required Ollama models | None currently listed | Live ReAct and embeddings are not ready |
| Active Chroma retrieval build | None in SQLite | Dense retrieval health cannot be `ready` |
| Docker CLI | Installed | Docker commands are available in principle |
| Docker daemon | Not running | Image build and Linux container smoke were not executed |
| Internet/Nager | Available during snapshot | Live Nager evidence passed |

## Canonical module state

Nine claimed modules are recorded as **Met**. Three are **Implemented / Live gate pending**:

1. Chroma RAG — requires a built and active Chroma collection plus live retrieval demonstration.
2. ReAct Agent — requires configured Ollama models and a live ready-state dialogue run.
3. Dockerization — requires an active Docker daemon, image build, and Linux container smoke.

SQL Agent remains **Unclaimed / Out of scope** by design.

## Known limitations and non-claims

- This is synthetic educational evidence, not real BDO or production evidence.
- The benchmark is deterministic contract/subsystem evaluation, not a live-model statistical study.
- Demo role namespaces are not production authentication or RBAC.
- OCR quality varies by scan and host environment; ambiguous cases route to retry or review.
- A `Complete` certificate result does not mean authentic, medically valid, approved, or submitted.
- Production adoption would require identity, security, privacy, retention, HR/legal/medical governance, user research, live-model evaluation, and operational review.

The remaining executable work is listed in [ImplementationPlanToDoLeft.md](ImplementationPlanToDoLeft.md). The canonical long-lived state remains `ContextKnowledgeBase/ProjectState.md` and `ContextKnowledgeBase/ModuleChecklist.md`.
