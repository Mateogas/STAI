# AISHA Business Case

> AISHA is a fictional educational capstone. It is not affiliated with, endorsed by, or representative of BDO Unibank. The Hire, policies, workflow records, certificate examples, and evaluation evidence are synthetic.

AISHA—AI Support for Hires and Associates—is a local-first assistant for three common onboarding decision areas: Payroll, Resource Access, and HR Policies. Its purpose is to help one fictional Hire, Alyssa Reyes, understand which current rule applies, what evidence supports the answer, and when a human must take over. It is support, not surveillance.

## Problem and wedge

Onboarding questions are often consequential but deceptively simple: when a payroll cutoff applies, which access route to use, or whether an HR policy covers a particular work site and employment classification. A generic chatbot can produce fluent text, but fluency is not enough. The user needs an answer tied to the active source version and confirmed profile facts, and the organization needs consent and privacy boundaries that cannot be bypassed by prose.

AISHA’s wedge is a narrow, testable decision-support loop:

1. resolve the one active immutable handbook build;
2. retrieve eligible evidence inside one of three topics;
3. evaluate applicability against four HR-confirmed attributes;
4. validate each material claim and structured citation;
5. clarify, abstain, or offer a human route when the evidence is insufficient.

This scope is deliberately more useful than an unrestricted HR chatbot. Narrow boundaries make it possible to prove what happens when evidence is missing, profile facts are unknown, a user asks for a human, a certificate contains sensitive content, an external calendar service fails, or telemetry shipping is unavailable.

## Product capabilities

| Need | AISHA v1.0 response |
|---|---|
| Payroll, access, or HR-policy question | Grounded Answer, Clarification Request, Abstention, or Escalation Offer from one typed policy contract |
| Applicability | Deterministic evaluation of Role Key, Department Key, Employment Classification, and Work Site |
| Human support | Privacy-safe offer first; an HR case exists only after explicit Hire consent |
| Profile correction | One-attribute change request; HR approval creates a versioned revision |
| Holiday fact | Read-only Philippine lookup for the simulated current/following year with `Based on Nager.` attribution |
| Certificate check | Local structural/completeness check after acknowledgement, with result-only History |
| Hire continuity | Server-owned ordered policy conversations that never override profile authority |
| HR visibility | Consented case summaries, attribute requests, and currently shared safe validation-result metadata—never raw policy chat or certificate contents |

## Privacy and trust design

Trust is part of the product, not a disclaimer added at the end. HR cannot browse Alyssa’s Policy Conversations. Chat cannot silently convert an informal statement into an authoritative profile fact. Escalation is offer-before-case, and certificate results are share-before-HR-view. Sharing can be revoked and a result can be deleted.

Certificate Check is especially bounded. It can identify whether required fictional demo fields appear and are structurally consistent, but it cannot authenticate a certificate, assess health, approve employment, or submit a document. Processing is local. Public history excludes document bytes, filename/MIME details, extracted text and values, diagnosis, confidence, and fingerprint. The original belongs in a separate fictional Official HR Document Route.

Operational monitoring follows the same principle. AISHA records closed schema-v2 metadata such as route, operation, outcome, counts, and timing. It does not record Hire identity, message text, policy text, certificate content, extracted values, or raw errors. The protected path remains local bounded JSONL to a batch shipper, then an authenticated relay and separate MLflow server. A telemetry failure cannot fail the user operation.

## Value hypothesis

The capstone does not claim measured production ROI. Its falsifiable value hypothesis is that an evidence-grounded, profile-aware assistant can reduce time spent locating the right onboarding rule and route while reducing risky improvisation. Useful future measures would include time to supported resolution, clarification rate caused by missing authoritative attributes, abstention quality, consented human-routing completion, and repeated-question reduction. Those measures should remain aggregate and must not turn private conversation into employee surveillance.

The likely operational benefits are:

- fewer inconsistent answers caused by stale or inapplicable policy pages;
- quicker routing when the handbook cannot resolve a case;
- less duplicate work from replay-safe API commands and server-owned history;
- clearer separation between self-service guidance and official HR decisions;
- safer local handling of a narrowly scoped certificate completeness check;
- auditable regression gates across evidence, privacy, consent, and deployment.

## Why this architecture

- **Deterministic handbook publication** makes the 108-page source, manifest, and page-native RAG records reproducible.
- **Chroma hybrid retrieval** supplies candidates while deterministic eligibility and applicability gates remain authoritative.
- **LangChain/LangGraph ReAct orchestration** demonstrates bounded tool selection without giving the model direct state mutation or arbitrary SQL.
- **SQLite** provides durable local normalized state, revisions, consented workflows, idempotency, and ordered memory.
- **Streamlit and FastAPI** expose the same shared service semantics for an accessible demo and a typed integration contract.
- **Local extraction/OCR** prevents certificate contents from being sent to a hosted model or external service.
- **Docker** makes the Python, OCR, permissions, and state-volume assumptions reproducible on Linux.

## Evaluation and limits

The frozen safety benchmark contains 60 synthetic cases: 18 policy/applicability, 12 retrieval, 6 API, 8 Nager, and 16 medical/privacy. Forty cases are Locked and twenty are Diagnostic. The selected P3 prompt achieved a Locked composite safety score of 0.987481, every component exceeded 0.85, and no hard gate failed. P1 and P2 remain published so selection is inspectable.

This is deterministic contract evidence, not a live-model accuracy study. It does not establish statistical confidence, production readiness, security certification, accessibility conformance, legal compliance, or performance on real BDO policies or people. The demo has one fictional Hire namespace, one active handbook version, no SSO/production authorization, no HRIS integration, and no official certificate workflow. These limits are explicit because the business case depends on earning trust, not inflating scope.

## Capstone success criterion

AISHA succeeds when the demo can reproducibly show that a supported policy question is grounded and applicable, an unsupported question abstains, an unknown deciding fact triggers one focused clarification, human support requires consent, private certificate contents do not enter chat or public history, telemetry remains metadata-only, and the same contract passes tests and a non-root Linux container smoke. The canonical module acceptance matrix records the owner, code, test, documentation, live step, and pass criterion for each claimed course module.
