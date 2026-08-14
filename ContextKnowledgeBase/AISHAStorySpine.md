# AISHA v1.1 Story Spine

## Canonical statement

AISHA—AI Support for Hires and Associates—is a local-first educational capstone for three onboarding topics: Payroll, Resource Access, and HR Policies. The main character is Alyssa Reyes, one fictional Hire. AISHA is not affiliated with or endorsed by BDO Unibank, contains no real employee data, and is support—not surveillance.

AISHA helps Alyssa answer a narrow question safely: “Which current onboarding rule applies to my confirmed situation, what source supports it, and what should happen when the system cannot decide?” It does not act as a general HR chatbot.

## Source and profile authority

The active immutable 108-page synthetic handbook build is the only runtime policy authority. Its hashed source register records the Philippine government and legal sources that informed v1.1, but those sources are not real BDO internal policy and are never fetched as runtime answer authority. A displayed policy claim must map to an eligible page by policy ID, revision, handbook version, page, and artifact identity. A reviewed Published Policy Clarification may supplement a linked policy but never contradict or replace it; a rule change requires a new handbook revision. A citation is not proof by itself; integrity, authority, status, topic, applicability, and claim validation must all pass.

Alyssa’s applicability profile has four HR-confirmed attributes: Role Key, Department Key, Employment Classification, and Work Site. Conversation statements do not update them. If an unknown attribute can change the answer, AISHA asks one focused clarification and makes no personalized conclusion. A correction is a one-attribute request and HR approval creates a versioned profile revision.

## Four policy outcomes

Every policy turn ends as one typed outcome:

1. Grounded Answer—eligible applicable evidence supports all material claims.
2. Clarification Request—one missing confirmed attribute can change applicability.
3. Abstention—the active eligible evidence cannot support a conclusion.
4. Escalation Offer—eligible policy evidence answers part of the question but leaves a material Evidence Gap appropriate for HR.

An offer is not a case. A bare request to “ask HR,” a Handbook Omission, an unsupported topic, or a Knowledge Index Outage does not qualify. Only Alyssa’s explicit consent creates an HR-visible case. Before consent, AISHA states that the existing parent Policy Conversation and its future messages will be copied into a child Case Thread while the case remains open. HR works in the Mediated Case: it can request one missing fact for AISHA to ask, add private notes, and decide a typed resolution. It does not join the Hire conversation by default. Direct human conversation requires a separate HR offer and Alyssa consent. HR cannot browse unrelated Policy Conversations or private certificate content.

## Certificate story

Certificate Check is a separate destination. Before processing, Alyssa sees and acknowledges that it is a local structural/completeness check—not authenticity, approval, medical assessment, diagnosis, or submission. PDF, JPG, and PNG files pass deterministic size, page, structure, and active-content gates. Extraction and OCR are local.

History retains only a safe result. It excludes file bytes, filenames, MIME details, extracted text and field values, diagnosis, confidence maps, and raw fingerprints. A result can be shared with HR, revoked, or deleted. HR sees only currently shared safe result metadata. The original belongs in a separate fictional Official HR Document Route.

## Product journeys

### Ask AISHA

Alyssa can create and reopen multiple named Policy Conversations. She asks about PAY-001 and receives a grounded result with claim-local structured evidence. An unsupported question abstains without creating HR work. An ACC-006 fixture with unknown Work Site asks exactly one deciding question. A holiday lookup uses only Philippine current/following-year facts and displays `Based on Nager.` Asking where to find a handbook-named but unspecified payroll route produces an evidence-gated offer; consent creates a Case Thread beneath the originating conversation. The thread shows unread and workflow status, mirrors later parent messages while open, and lets Alyssa answer AISHA's structured questions for HR.

### Profile revision

Alyssa requests one Work Site change. HR approves or rejects against the expected version. Approval adds a revision; neither chat nor the agent directly writes the confirmed profile.

### Certificate and History

Alyssa acknowledges the boundary, uploads a synthetic labelled PDF, and receives `Complete`. She can share the safe result, view HR’s corresponding structured record, revoke sharing, and delete her result. `Complete` never means genuine, medically acceptable, approved, or submitted.

### HR User

HR sees consented Mediated Cases, attribute change requests, and currently shared safe validation results. HR cannot browse the Policy Conversation store directly: it sees only the copied conversation attached to a case after Alyssa accepts the explicit sharing notice. It asks for missing facts through AISHA rather than entering the chat, and separate consent is required for exceptional direct conversation. HR has no route for unrelated conversations, certificate bytes, extracted content, or medical detail. Resolving a case records its type and scope; AISHA communicates the decision as Case Resolution Memory and stops future parent-message mirroring. AISHA can answer related follow-ups inside the resolved thread. A proposed reusable clarification requires a separate policy-owner review; case exceptions remain case-scoped and Policy Amendment Candidates wait for a new handbook revision.

## Evaluation story

The frozen benchmark has 60 synthetic cases across policy/applicability, retrieval, API, Nager, and medical/privacy. P1 fails the Locked gate, P2 passes, and P3 is selected at Locked CSS 0.987481 with every component at least 0.85 and zero hard failures. This is deterministic contract evidence, not live-model or production validation.

The final demonstration closes with the integrated acceptance report and non-root Linux container smoke. The module matrix claims twelve course modules with named owners and leaves SQL Agent explicitly unclaimed.
