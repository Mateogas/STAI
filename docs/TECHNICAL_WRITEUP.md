# AISHA v1.1 Technical Write-up

## Abstract

AISHA—AI Support for Hires and Associates—is a local-first educational capstone that demonstrates evidence-grounded onboarding decision support. It is limited to three topics: Payroll, Resource Access, and HR Policies. The product serves one fictional Hire, Alyssa Reyes, and uses only synthetic policies, profiles, records, certificate examples, and evaluation cases. AISHA is not affiliated with or endorsed by BDO Unibank, and it must not be interpreted as a production HR, medical, or banking system.

The refactor described here replaces a broad assistant concept with a narrow set of enforceable contracts. A policy response must be one of four typed outcomes; a successful consent is a separate typed workflow confirmation. Applicability is determined from four HR-confirmed profile attributes. Evidence comes from one active immutable 108-page handbook build. Human routing requires explicit consent. Certificate checking is a local completeness-only process with result-only history. Streamlit and FastAPI use one shared turn-processing module. Privacy-safe schema-v2 operation metadata travels through the existing protected observability topology. A frozen 60-case safety benchmark, a six-turn production regression, and a Linux container smoke make those claims reproducible.

The important design decision is that generated prose is not the authority. Deterministic code owns identity, evidence eligibility, applicability, consent, state versions, certificate gates, public projections, idempotency, and acceptance. The model is useful inside those boundaries: it classifies normal input, selects a small bounded tool set, and drafts a candidate structured response. If any consequential validation fails, the system returns a safe typed outcome rather than exposing an unsupported conclusion.

## 1. Problem framing and requirements

New hires encounter short questions with organizational consequences: which payroll rule covers a date, which resource-access procedure applies, or whether an HR policy covers their role and work site. A generic conversational model may answer fluently even when it has found a stale page, ignored an applicability condition, or invented a route. A document-search demo can also appear grounded while citing text that is not authoritative or does not apply to the person asking.

AISHA therefore treats the problem as decision support rather than general question answering. A useful response needs five properties. First, it is inside one of the three supported topics. Second, it uses the currently active handbook identity. Third, every material claim has eligible page-native evidence. Fourth, the policy applies to confirmed profile facts or the system asks for the one missing fact that can change the result. Fifth, the response communicates uncertainty through clarification, abstention, or a consent-first human route.

Privacy requirements are equally central. HR cannot browse the Policy Conversation store. Informal chat cannot modify the authoritative profile. An escalation offer does not itself create a case. HR sees a Mediated Case only after explicit consent that discloses how the linked parent history and future parent messages will be copied while the case is open. HR requests missing facts through AISHA and supplies a typed resolution; it does not enter Hire chat by default. Unrelated conversations remain inaccessible. Certificate content is more restricted: it must be routed away from policy chat before persistence, processed locally, and omitted from public history and telemetry. Monitoring must be operationally useful without introducing stable employee tracking or content collection.

The implementation was organized into twelve dependency-ordered slices: domain contracts; deterministic handbook publication; normalized persistence; immutable hybrid retrieval; grounded policy core; bounded Nager integration; local certificate validation; consented journey orchestration; typed v1 API; Streamlit journeys; privacy-safe telemetry and benchmark; and final legacy replacement, documentation, and acceptance. Each slice began with failing tests and was committed only after its focused suite passed. This ordering allowed later surfaces to reuse already-tested contracts rather than inventing separate behavior.

## 2. Domain model and response contract

The domain vocabulary is intentionally small. `HireProfile` contains Role Key, Department Key, Employment Classification, and Work Site. These are HR-confirmed attributes with a resource version. Conversation memory can help interpret a follow-up but is never authoritative for these fields. A correction travels through an `AttributeChangeRequest` that changes exactly one attribute. HR approval creates a new profile revision; rejection leaves the current revision unchanged.

Policy interaction returns a discriminated `PolicyResponse`. `GroundedAnswer` contains validated claims and structured citations. `ClarificationRequest` asks one focused question when an unknown constraining profile attribute can change applicability. `Abstention` states that eligible evidence cannot support an answer. `EscalationOffer` requires a deterministic `EscalationEligibility` result: eligible partial evidence, one material Evidence Gap, a related policy identity, and a bounded human route. These shapes prevent downstream code from guessing the meaning of arbitrary text or turning every help request into HR work.

Structured evidence includes policy ID, policy revision, handbook version, page number, and immutable artifact identity. It deliberately excludes stored raw snippets and model-authored filenames. Claim validation checks that each material statement maps to evidence from the active version and an applicable policy record. A citation is not added merely because retrieval ran; an unsupported result abstains without decorating it with an unrelated source.

Other workflow objects follow the same rule. Escalation offers and cases are distinct. Validation results contain a safe status and lifecycle metadata rather than certificate content. External calendar results contain bounded facts, attribution, and cache/fallback state. API responses use safe success and error envelopes. Telemetry accepts only closed event, route, operation, outcome, count, duration, and experiment values. Narrow models make privacy and behavior testable at every boundary.

## 3. Deterministic handbook and retrieval

The synthetic handbook is authored as structured YAML and published into three connected artifacts: a deterministic 108-page PDF, a page manifest, and page-native JSONL records for retrieval. The build uses invariant PDF generation so the same source produces the same artifact hash. Every RAG record includes the handbook artifact hash, manifest hash, page content hash, page identity, policy identity and revision, topic, status, effective date, claim types, applicability constraints, and route metadata.

Publication verification checks the PDF page count, manifest count, RAG record count, unique record identities, and hash agreement. Ingestion stages a new immutable build, validates it completely, then changes the active pointer atomically. A failed or partial build cannot become active. Previous build identities remain available for audit and rollback rather than being overwritten in place.

Retrieval uses Chroma vector candidates and deterministic lexical candidates. Candidate generation is not authorization. Records pass version and integrity checks, then authority, status, topic, and applicability eligibility gates. The system distinguishes retrieval failure types so an empty result, integrity mismatch, unavailable index, and ambiguous applicability do not collapse into one misleading answer. This design lets Chroma satisfy the selected RAG course module while deterministic code retains the consequential decision boundary.

Page-native records solve two common citation problems. They avoid chunks that span artificial page boundaries, and they make a displayed page number traceable to the published PDF. The result remains an educational synthetic source rather than a real company policy. Its purpose is to demonstrate that provenance can be reproducible and claim local.

## 4. Policy core, prompts, and bounded ReAct

Three prompt variants—P1, P2, and P3—are frozen and evaluated under identical settings. Temperature is zero and the agent seed is fixed. The prompts do not ask the model to reveal private chain-of-thought. Instead, they define the supported topics, tool boundary, response schemas, evidence obligations, and safe failure behavior. P3 was selected by the predeclared benchmark rule after all variants were evaluated; the selection was not made by subjective preference.

`PolicyTurnEngine.handle_turn(conversation_id, message)` is the one production seam used by Streamlit, FastAPI, and turn-level tests. After the injection/off-topic boundary, every supported turn enters a fresh ReAct loop with bounded conversation and pending-offer context. ReAct determines dialogue act and goal, revises searches, reads full policy bundles, checks applicability, and distinguishes supported from unresolved portions. Its result is finalized into a typed plan and typed response draft. `RunCapture` records closed tool identities, exact ephemeral page contents, and applicability checks; deterministic code then validates active handbook identity, citations, exact claim excerpts, applicability, privacy, Evidence Gap eligibility, and consent. State-changing operations remain deterministic application commands rather than agent tools.

The active Chroma adapter supplies dense candidates to weighted lexical retrieval. ReAct chooses the query and can search again or read every page for an exact policy ID. A candidate with a valid citation shape but an uncaptured, inapplicable, inactive, or wrong-topic page is rejected before display. Chroma or Ollama failure is surfaced; there is no production lexical or deterministic answer fallback.

Input-classifier availability, output schema validation, evidence eligibility, applicability, citation identity, exact claim support, escalation eligibility, consent, versions, clarification promotion, and certificate privacy all fail closed. Off-topic and prompt-injection classifications return scoped results without exposing system instructions. A malformed or unavailable required model cannot trigger a local answer composer.

Disambiguation is based on whether an unknown confirmed attribute constrains the candidate policy. If Work Site can change whether ACC-006 applies, and Work Site is unknown, AISHA asks one question about Work Site. It does not re-ask known facts, infer the answer from conversation text, ask multiple broad questions, or mutate the profile. Once HR confirms a profile revision, later turns use the new version.

## 5. Nager.Holidays integration

The external-tool module is intentionally read only. AISHA calls Nager.Holidays only for Philippine public-calendar facts and only for the simulated current or following year. It sends no Hire ID, profile, conversation text, policy content, certificate data, OCR output, or medical information. A successful live result is displayed with the exact attribution `Based on Nager.`

Nager supplies calendar facts, not employment-policy consequences. The policy core remains responsible for stating what a date means under an eligible handbook page. Response validation rejects the wrong country or year and unexpected payloads. The service implements bounded retry, seven-day cache, circuit behavior, conflict handling, and handbook/human fallback. External availability is isolated from application health, so a Nager outage cannot make `/api/v1/health` fail or cause a fabricated date conclusion.

## 6. Certificate Check and privacy

Certificate Check is a separate destination rather than a conversational shortcut. Before file selection, the interface explains that AISHA performs only a local structural/completeness check. It does not authenticate a document, assess health, diagnose, approve employment, or submit anything to HR. The user must acknowledge that boundary before processing.

Deterministic pre-processing gates restrict file type to PDF, JPG, or PNG; size to 10 MB; PDF length to three pages; and reject malformed, encrypted, active-content, or otherwise unsafe structures. Rejection at this stage creates no validation-result record. Accepted PDFs use local text extraction; images and image-only pages can use local Tesseract English OCR. A deterministic labelled-field parser evaluates the synthetic required fields. No hosted model or external OCR service receives content. A dedicated bounded Certificate Agent may invoke only policy confirmation and local validation tools; the model receives typed status/codes, never document bytes, filenames, OCR text, or extracted values. If its exact two-tool sequence is unavailable or invalid, deterministic validation remains authoritative and the public trace is labelled `deterministic_degraded`.

`Complete` and `Incomplete` are completeness outcomes, not authenticity judgments. A retryable processing failure may issue one short-lived opaque retry token. A failed retry ends in `Needs Human Review` and exposes only an ephemeral blank Manual Field Summary template. If a user completes that template outside AISHA, completed values never return to this system. The official document remains destined for a separate fictional Official HR Document Route.

Persistence retains only safe result metadata required for History and lifecycle actions. It excludes document bytes, filename and MIME details, extracted text, extracted values, diagnosis, confidence maps, and the raw document fingerprint. A keyed local fingerprint supports short-window duplicate detection, but its installation secret resides outside SQLite and is created with restrictive permissions. History allows explicit share, revoke, and delete actions. HR can view only currently shared safe result metadata, never the file or extracted content.

## 7. Persistence, memory, consent, and reset

SQLite is used as deterministic application state, not as an LLM-generated SQL surface. Schema epoch 6 adds Case Information Requests and separately consented direct-conversation mode to Evidence Gaps, typed Case Resolution Memory, Case Threads, messages, events, and notifications. Schema epoch 7 adds only the Certificate Agent execution mode and its closed action sequence. It stores no retrieved snippets, rewritten queries, document content, or hidden reasoning. Connection-per-operation behavior remains suitable for Streamlit threads on both POSIX and Windows; installation locking and database cutover use platform-specific safe primitives.

Policy messages are ordered by server-assigned sequence. API clients submit only a new message; they cannot submit arbitrary prior turns or overwrite conversation history. An Idempotency-Key binds a command fingerprint to its prior response so retries return the same semantic result. Reusing a key for a different command is rejected. Cursor pagination has fixed bounds and stable ordering.

Consent is represented as deterministic state progression. ReAct may propose an
Evidence Gap only after separating the supported and unresolved portions of a
question. Deterministic code then verifies that the cited partial evidence was
captured in the same run, that the known excerpt is exact, and that the gap is
one of missing procedure, unclear exception, policy conflict, or unclear route.
A bare help request can only return an already-pending eligible offer; it cannot
manufacture one. Explicit language such as “route it please” counts only when
that pending notice has already been shown. Consent backfills the ordered parent
history into a child Case Thread and later Hire/AISHA parent messages are
mirrored while open. HR may create one structured Case Information Request,
AISHA asks it in the Hire thread, and the linked Hire answer returns the case to
HR. HR resolution records a type, scope, and reuse state; AISHA communicates it
and disables mirroring. Direct human conversation requires its own offer and
Hire consent. Related closed-thread questions use the resolution directly. Only
a reviewed non-case-only Policy Clarification can supplement a later grounded
answer; Case Exceptions stay thread-only and Policy Amendment Candidates remain
pending handbook publication.

The Full Demo Reset is an explicit destructive product action. It clears product state, restores the fictional Alyssa seed and active handbook pointer, rotates the certificate fingerprint key, and re-establishes required directories. It accurately states its limits: it does not claim to erase already shipped bounded telemetry or external backups. Automated reset tests verify state and key rotation.

## 8. UI and API surfaces

Streamlit presents role and destination separately. The Hire can choose Ask AISHA, Certificate Check, or History. Ask AISHA retains the approved navy, blue, gold, paper, and canvas visual system while adding a ChatGPT-style list of reopenable conversations. Each consented HR ticket appears Discord-style beneath its originating chat with unread count and workflow status. A persistent banner identifies parent chats being shared. HR sees the copied thread, selects Resolution Type and Scope, may propose eligible clarification reuse, and performs a separate demo policy-owner review. Resolved threads expose a distinct AISHA follow-up input. Visible status text does not rely on color alone, controls are designed for keyboard access and 44-pixel targets, dynamic outcomes use status regions, and the layout is exercised at 320 CSS pixels as well as desktop width.

FastAPI exposes only `/api/v1`. The contract includes health; conversation create, list, message, detail, and delete; escalation consent; conversation-linked case listing; Hire and HR Case Thread reads; HR information requests; direct-conversation offer/consent; typed HR resolution; clarification approve/reject review; attribute request and HR decision operations; certificate validate and retry; validation-result list, detail, share, revoke, delete; and HR shared-result reads. Legacy unversioned paths are absent. OpenAPI uses typed request and response models, consistent `{data, meta}` and `{error, meta}` envelopes, privacy-safe errors, configured CORS, Alyssa-only demo namespaces, resource versions, cursor bounds, and idempotency semantics.

Both surfaces cross the same `PolicyTurnEngine` interface through `AishaService`. This is important for acceptance: the UI cannot quietly provide a weaker context, relevance, or consent rule than the API. Tests replay the original six-turn production failure through the module and API, reject a wrong-topic agent candidate, inspect OpenAPI for forbidden fields, replay idempotent messages, close cases, revise attributes, and exercise the complete certificate lifecycle.

Health describes service availability and handbook activation without treating
optional Nager or telemetry as required dependencies. The endpoint remains
responsive for diagnosis, but it returns HTTP 503 with `status: unavailable`
when SQLite, the active Chroma build, the agent model, or the classifier model
is not ready. Streamlit's `/_stcore/health` is only process liveness and must not
be used as the production dependency-readiness probe.

For production, Ollama is external and must provide `llama3.1:8b`,
`qwen2.5:3b-instruct`, and `nomic-embed-text`. The application uses an
8192-token agent context window, a six-model-call ReAct research budget, and
a graph recursion limit of 32 by default. The separate graph limit leaves room
for middleware and tool nodes. New persistent volumes must run the immutable
ingestion command before serving traffic. There is no `STAI_AGENT_ENABLED`
switch and no supported model/index answer fallback.

## 9. Privacy-safe LLMOps

The existing four-stage topology is preserved: application observability writes local JSONL, the log shipper batches records, an authenticated relay validates and maps them, and a separate MLflow server stores runs. Only additive safe changes were made. Schema v2 records use random event IDs and closed metadata. Fixed experiments separate prompt, retrieval, safety, external-tool, API, and medical operations without embedding user identity in names.

The sanitizer can accept older v1 records only by projecting them into the v2 allowlist. Unknown fields are dropped or rejected, and forbidden content-like keys cause quarantine. Counts preserve the distinction between absent and zero. Local files are bounded to seven days and 100 MB. Shipping supports partial acknowledgement: accepted event IDs advance, retryable events remain queued, and permanent invalid records are quarantined. The relay uses event-ID idempotency so a network retry does not create duplicate MLflow runs.

Telemetry is a side effect with total failure isolation. File errors, relay unavailability, authentication failure, malformed acknowledgement, and MLflow failure cannot change the policy, case, attribute, certificate, or API result returned to the user. Tests assert denylisted fields and raw values never appear in local records, shipped payloads, relay tags, or OpenAPI.

## 10. Evaluation method and results

The frozen benchmark contains exactly 60 synthetic cases: 18 policy/applicability, 12 retrieval, 6 API, 8 Nager, and 16 medical/privacy. Forty cases are Locked acceptance evidence and twenty are Diagnostic. Six component scores—G, R, A, D, M, and X—are combined with a weighted harmonic mean so one weak safety dimension cannot be hidden by strong average performance. The Locked gate requires composite safety score at least 0.90, every component at least 0.85, and zero hard failures.

All three prompt variants run three prompt-dependent repetitions under the same frozen inputs. The published results retain failures as well as successes. P1 scored 0.88 and failed. P2 scored 0.955474 and passed. P3 scored 0.987481, all component thresholds passed, and no hard gate failed, so the declared selection rule chose P3. The execution mode is honestly labelled `offline_deterministic_contract`; this benchmark verifies implemented contracts and regression behavior, not live-model accuracy.

The final extension also supplies a separate local LLM-as-judge path for the canonical six-turn regression. A hardware-configurable local Qwen judge receives synthetic questions, typed candidates, authoritative deterministic contract facts, and predeclared case-specific reference criteria. The recorded v1.2 run used an explicit CPU-only profile, but production remains free to use available acceleration. Objective outcome/policy checks remain deterministic; the judge scores grounding, relevance, action quality, and safety under a closed 1–5 rubric. Raw prompts and answers are ephemeral. The persisted v1.2 report contains only case IDs, closed scores/failure codes, aggregates, model identity, and execution mode.

The integrated acceptance runner rebuilds and verifies the handbook, reruns the benchmark and selection, scans OpenAPI and SQLite for forbidden surfaces, scans production code for replaced legacy contracts, validates documentation and named ownership, runs the full offline test suite, records a genuine live Nager result, builds the Docker image, and executes the Linux container smoke. The smoke launches Streamlit and FastAPI as non-root UID 10001, checks both health paths, proves PAY-001 behavior, uploads a synthetic certificate that deterministically returns `Complete`, and checks restrictive key permissions.

## 11. Course modules and ownership

Twelve course modules are claimed with current evidence: Prompt Engineering, Structured Outputs, Disambiguation, Chroma RAG, Memory, Guardrails, ReAct Agent, External Tool Use, Chat UI, API Endpoint, LLMOps Monitoring, and Dockerization. Johann Casio owns Prompt Engineering, Chroma RAG, External Tool Use, and Dockerization. Jose Miguel Espinosa owns Structured Outputs, Disambiguation, Guardrails, and LLMOps Monitoring. Bon Aquino owns Memory, ReAct Agent, Chat UI, and API Endpoint.

SQL Agent is explicitly unclaimed. Although AISHA uses SQLite, queries are handwritten repository operations and no model receives an arbitrary SQL-generation capability. The canonical module matrix records, for every claimed module, the final claim, production code, automated test, documentation or evaluation, live demo step, pass criterion, status, and named owner. No row can override a failing cross-cutting privacy, consent, evidence, reset, telemetry, benchmark, or container gate.

## 12. Limitations and conclusion

AISHA v1.1 is intentionally not a production system. It has one fictional Hire namespace, one synthetic handbook version, no SSO or production authorization, no HRIS or document-management integration, no official approval workflow, and no production load evidence. The accessibility walkthrough demonstrates design intent and manual checks but is not an accessibility certification. The live Nager proof demonstrates bounded connectivity at one time, not a service-level guarantee. The safety benchmark is synthetic and deterministic, so its numerical score must not be generalized to real policies, populations, or live-model performance.

Within those limits, the refactor demonstrates a coherent engineering claim: a model-assisted onboarding experience can remain useful without making model prose authoritative. Immutable evidence, deterministic applicability, typed outcomes, consented mutations, result-only sensitive history, privacy-safe telemetry, replay-safe APIs, and reproducible Linux acceptance form one connected safety boundary. The final artifact is smaller in topic scope than a general HR assistant, but deeper in the places that matter for trustworthy decision support.
