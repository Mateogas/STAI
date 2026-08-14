# AISHA Project State

AISHA is now a local-first, three-topic onboarding-policy capstone for Payroll, Resource Access, and HR Policies. The one seeded Hire is Alyssa Reyes. All BDO context is fictionalized and educational; the project has no affiliation, endorsement, real employee data, or internal-system access.

Implemented production boundaries:

- One canonical 108-page AISHA Handbook v1.0 generated from normalized YAML, with page manifest, immutable RAG page records, hashes, and a publication report.
- Immutable hash-named Chroma builds, hybrid lexical/dense candidates, deterministic authority/applicability gates, verified activation, rollback, and metadata-only citations.
- Four typed Policy Responses: Grounded Answer, Clarification Request, Abstention, and consent-first Escalation Offer.
- A normalized SQLite epoch 5 for Alyssa's confirmed profile, ordered policy conversations, safe typed turn context/results, claim/citation metadata, evidence-gated offers, consented Case Threads/messages/events/notifications, structured resolution memory and review state, attribute revisions, Validation Results, retry/idempotency state, holiday cache, retrieval pointer, and safe reset.
- Local certificate preflight, PDF text or image OCR, deterministic name/date/duration rules, one retry, result-only persistence, private-by-default history, and explicit share/revoke/delete.
- A versioned `/api/v1` surface with safe envelopes, configured CORS, fixed simulated dates, server-owned history, idempotent replay, versions, cursors, role-separated demo namespaces, and one health endpoint.
- Streamlit Ask AISHA, Certificate Check, History, and HR structured views with reopenable conversations, nested child Case Threads, shared-parent banners, HR replies and internal notes, typed resolution scope/reuse review, resolved-thread follow-ups, responsive layout, keyboard focus, status, and announcement evidence.
- One shared `PolicyTurnEngine` that resolves bounded follow-up context, hard-gates retrieval by topic, rejects subject-level handbook omissions, invokes ReAct when Ollama is ready, safely degrades to verified deterministic composition, and offers HR only for a deterministic material Evidence Gap.
- A v1.1 six-turn production regression across the module, API, and Linux container smoke; wrong-topic citations are hard failures.
- Nager.Holidays as a bounded Philippines-only current/following-year tool with exact `Based on Nager.` attribution, seven-day cache, retry, validation, circuit breaker, and offline fallback.
- Schema-v2 privacy-safe operational telemetry over the preserved JSONL → rotating shipper → authenticated relay → separate MLflow topology.
- A frozen 60-case, 40/20 Composite Safety Benchmark with P1/P2/P3 reports and P3 selected by the locked tie-break.
- A non-root Linux container with Tesseract English and a full UI/API/policy/certificate smoke.

Legacy ramp/task/pulse/risk production paths, flat Markdown seed documents, multi-employee/org/plan data, filename citations, unversioned API routes, and employee-linked telemetry are removed. Historical discussion may remain only in context/changelog material clearly labelled as superseded.

The canonical completion command is `uv run python -m stai.acceptance`; the canonical module status is `ContextKnowledgeBase/ModuleChecklist.md`.

The v1.1 implementation passes the offline suite and dialogue contract. The
current workstation has no active Chroma build, no pulled Ollama models, and no
running Docker daemon, so Chroma, live ReAct, and the revised container smoke
remain explicit per-release live gates rather than completed evidence.
