# AISHA Three-Topic Refactor — Completed Implementation Plan

The 12 authoritative slices from GitHub issue #1 were implemented test-first in dependency order. Each slice exited only after its focused tests and the then-current full suite passed, and each has its own commit.

| Slice | Result | Commit | Exit evidence |
|---|---|---|---|
| 1. Contract fixtures and domain types | Complete | `0bd45f0` | Typed outcome and frozen 60-case fixture validation |
| 2. Handbook artifact | Complete | `9692cfa` | Deterministic 108-page publication gates |
| 3. Normalized persistence and cutover | Complete | `d329c19` | Schema/cutover/reset/key/privacy tests |
| 4. Versioned retrieval | Complete | `6626e9f` | Immutable build, gates, activation/rollback tests |
| 5. Policy core | Complete | `3126d0d` | Applicability, structured response, grounding, prompt and tool tests |
| 6. Nager external tool | Complete | `0b93940` | Eight behavior families plus offline/cache/circuit tests |
| 7. Medical validation | Complete | `7094f26` | Policy-before-file, local extraction/OCR, deterministic validation and privacy tests |
| 8. Shared orchestration and memory | Complete | `b7b09b3` | Conversation, consent, attribute, and result lifecycle tests |
| 9. Typed `/api/v1` | Complete | `41b901d` | TestClient contract and privacy suite; legacy paths absent |
| 10. Dialogue Streamlit journeys | Complete | `cb9fede` | AppTest plus in-app responsive/accessibility walkthrough |
| 11. Telemetry v2 and benchmark | Complete | `f9a6b5b` | Observer/shipper/relay suites and P1/P2/P3 calibration |
| 12. Legacy removal, packaging, final evidence | Complete when acceptance report is `passed` | final slice commit | Full offline suite, locked benchmark, privacy scan, live Nager, Docker/Linux smoke, docs and ownership matrix |

No later work should reintroduce ramp plans, task/pulse/risk surveillance, filename citations, snippet-bearing evidence, arbitrary client history, automatic escalation, raw medical input retention, employee-linked telemetry, or compatibility aliases for `/chat`.

## v1.1 production dialogue remediation

| Slice | Result | Exit evidence |
|---|---|---|
| 0. Incident contract | Complete | Exact six-turn deployed transcript is a module/API regression fixture |
| 1. Deep turn seam | Complete | Streamlit and API delegate to `PolicyTurnEngine.handle_turn` |
| 2. Context and actions | Complete | Restart-safe topic/reference state and offer-before-chat-consent progression |
| 3. Retrieval repair | Complete | Stopword-safe weighted lexical plus active Chroma candidates and topic hard gate |
| 4. Production ReAct | Complete | Mandatory ReAct plan/response path with typed finalization and no local answer fallback |
| 5. Relevance validation | Complete | Structurally valid wrong-topic agent answers fail before display |
| 6. Persistence/replay | Complete | Schema epoch 3 safe typed result replay without snippets or hidden reasoning |
| 7. Acceptance/deployment | Implemented; external staging run required per release | Full suite, container transcript smoke, and explicit disposable-staging gate |

## v1.2 evidence-gated HR clarification memory

| Slice | Result | Exit evidence |
|---|---|---|
| 1. Domain and authority | Complete | Evidence Gap, Case Resolution Memory, clarification review, and amendment boundary recorded in glossary/ADR |
| 2. Persistence | Complete | Schema epoch 5 stores offer/case gaps and typed versioned resolutions |
| 3. Eligibility | Complete | Partial eligible evidence can offer; omissions, outages, unsupported subjects, and bare human requests cannot |
| 4. Thread memory | Complete | Related resolved-thread follow-ups use the HR resolution without reopening the case |
| 5. Reviewed reuse | Complete | Only approved non-case-only Policy Clarifications supplement later handbook-grounded answers |
| 6. Surfaces and acceptance | Complete when the full suite and responsive walkthrough pass | Streamlit, `/api/v1`, regression, persistence, and privacy evidence agree |

## v1.3 agentic policy and mediated-case remediation

| Slice | Result | Exit evidence |
|---|---|---|
| 1. Realistic Hire corpus | Complete | 65 researched-style payroll, HR, privacy, security, safety, and dialogue questions have closed Agent Plan expectations |
| 2. Semantic discovery | Complete | All-topic and scoped policy catalogs are built deterministically from active policy records |
| 3. Payroll and HR sub-intents | Complete | Pay schedule, payslip, changes, deductions, payment method, attendance, leave, privacy, certificate, conduct, and dress routes have executable regressions |
| 4. Handbook v1.1 | Complete | Existing 108-page publication updated in place and tied to a hashed authoritative-public-source register |
| 5. Bounded agent loop | Complete | Typed observe-plan actions plus closed read-only tools; deterministic validation and mutations remain outside model authority |
| 6. Mediated HR cases | Complete | Schema epoch 6 information requests, AISHA-coordinated Hire answers, HR notes/resolutions, notifications, and separate direct-conversation consent |
| 7. Surfaces and acceptance | Pending final gate | Streamlit, `/api/v1`, documentation, full tests, acceptance, and responsive walkthrough agree |

Production activation requires the three configured Ollama models, ingestion
into the same persistent data volume used by the running application, and an
HTTP 200 `ready` result from `/api/v1/health`. Streamlit's health route is a
liveness check only. There is no `STAI_AGENT_ENABLED` switch or supported local
answer fallback.
