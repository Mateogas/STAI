# AISHA Architecture Diagrams

These diagrams describe the implemented AISHA v1.0 educational capstone. AISHA covers only Payroll, Resource Access, and HR Policies for one fictional Hire, Alyssa Reyes. It is not affiliated with or endorsed by BDO Unibank and does not use real employee data.

## System boundary

```mermaid
flowchart LR
    subgraph Sources["Authoritative and bounded sources"]
        Handbook["Immutable 108-page handbook build"]
        Profile["HR-confirmed Hire Profile"]
        State["Normalized SQLite state"]
        Nager["Nager.Holidays PH calendar facts"]
        File["Local certificate file, transient"]
    end

    subgraph Core["Shared deterministic core"]
        Retrieval["Hybrid Chroma retrieval and eligibility gates"]
        Policy["Applicability and claim validation"]
        Agent["Bounded ReAct orchestration"]
        Consent["Consent and versioned workflow commands"]
        Medical["Local extraction and completeness rules"]
        Repo["Repository and ordered memory"]
    end

    subgraph Surfaces["Equivalent product surfaces"]
        UI["Streamlit: Ask, Certificate, History, HR"]
        API["Typed /api/v1 REST contract"]
    end

    subgraph Outputs["Privacy-safe outcomes"]
        PolicyResult["Grounded answer, clarification, abstention, or offer"]
        Case["Consented child Case Thread"]
        Attribute["One-attribute revision request"]
        Validation["Result-only validation history"]
        Telemetry["Closed schema-v2 operation metadata"]
    end

    Handbook --> Retrieval --> Policy --> Agent
    Profile --> Policy
    Nager --> Agent
    State <--> Repo
    File --> Medical --> Repo
    Agent --> Consent --> Repo
    Repo <--> UI
    Repo <--> API
    Agent --> PolicyResult
    Consent --> Case
    Consent --> Attribute
    Medical --> Validation
    Core -. "metadata only" .-> Telemetry
```

The policy answer is not whatever text a model happens to emit. Retrieval first resolves the active immutable build, combines vector and lexical candidates, then rejects records that fail version, integrity, authority, status, topic, or applicability gates. The policy core validates every material claim and citation before either surface can render it. The model can choose among bounded tools, but it cannot approve a profile revision, manufacture consent, decide certificate authenticity, or write arbitrary SQL.

## Policy turn flow

```mermaid
flowchart TD
    Start["Message with fixed simulated date"] --> MedicalRoute{"Certificate or medical content?"}
    MedicalRoute -- Yes --> RejectChat["Reject before conversation persistence; route to Certificate Check"]
    MedicalRoute -- No --> Classify["Input scope and injection classifier"]
    Classify --> Allowed{"Allowed?"}
    Allowed -- No --> Scoped["Typed scoped response"]
    Allowed -- Yes --> Context["Load bounded typed conversation context"]
    Context --> Resolve["Resolve topic, reference, dialogue act, and standalone query"]
    Resolve --> Action{"Policy turn or workflow action?"}
    Action -- "Offer or consent" --> Workflow["Deterministic versioned escalation command"]
    Action -- "Policy" --> Version["Get active handbook identity"]
    Version --> Search["Active Chroma plus weighted lexical candidates"]
    Search --> Found{"Eligible evidence?"}
    Found -- No --> Abstain["Abstention; no unrelated citation"]
    Found -- Yes --> Applicable{"All constraining attributes known?"}
    Applicable -- No --> Clarify["One focused clarification; no mutation"]
    Applicable -- Yes --> Claim["ReAct candidate or deterministic degraded composer"]
    Claim --> Validate["Schema, applicability, topic relevance, claim, and citation validation"]
    Validate --> Valid{"Valid?"}
    Valid -- No --> SafeAbstain["Fail-closed typed abstention"]
    Valid -- Yes --> Persist["Persist ordered safe outcome, context, and evidence identity"]
    Workflow --> Persist
    Persist --> Render["Render identical UI/API semantics"]
    Render --> OfferOnly["Offer precedes case; explicit consent is deterministic"]
```

Evidence exposed to users is structured identity—policy ID, revision, handbook version, page, and artifact hashes—not stored raw snippets or model-authored filename citations. Conversation history is server owned and ordered. Safe typed turn state resolves follow-ups across restarts, while conversation statements never become authority for Hire Profile attributes. A wrong-topic citation is invalid even when its page identity was retrieved.

## Consented Case Thread flow

```mermaid
flowchart LR
    Parent["Policy Conversation"] --> Offer["Escalation offer plus sharing notice"]
    Offer --> Consent{"Hire consents?"}
    Consent -- No --> Private["No case and no HR visibility"]
    Consent -- Yes --> Backfill["Copy existing parent history"]
    Backfill --> Thread["Child Case Thread"]
    Parent -- "Future Hire and AISHA messages while open" --> Thread
    Thread --> HR["HR reply or internal note"]
    HR -- "Hire-visible reply" --> Thread
    HR -- "HR-only note" --> HR
    Thread --> Resolve["Visible resolution summary"]
    Resolve --> Stop["Resolved; parent mirroring stops"]
```

The left navigation nests each Case Thread beneath its parent and shows text status and unread count. HR never queries the Policy Conversation tables through its product surface; the case workflow owns the copied thread, participant permissions, versions, events, and notifications. Certificate content and unrelated conversations never enter this path.

## Evidence-gated clarification and memory

```mermaid
flowchart TD
    Question["Supported-topic question"] --> Evidence{"Eligible policy evidence?"}
    Evidence -- "None, outage, or subject omitted" --> Abstain["Abstain; no HR offer"]
    Evidence -- "Complete" --> Answer["Grounded handbook answer"]
    Evidence -- "Partial" --> Gap{"Material Evidence Gap?"}
    Gap -- No --> Answer
    Gap -- Yes --> Offer["Consent-first HR clarification offer"]
    Offer --> Case["Shared Case Thread"]
    Case --> Resolution["Typed HR resolution"]
    Resolution --> ThreadMemory["Case Resolution Memory"]
    ThreadMemory --> Followup["Related resolved-thread follow-ups"]
    Resolution --> Type{"Resolution Type"}
    Type -- "Case Exception" --> CaseOnly["Thread only"]
    Type -- "Policy Amendment Candidate" --> Handbook["Wait for new handbook revision"]
    Type -- "Policy Clarification" --> Review{"Policy-owner review"}
    Review -- Reject --> CaseOnly
    Review -- Approve --> Published["Published Policy Clarification"]
    Published --> Supplement["Supplement later cited handbook answers"]
```

The model never decides that it is merely “unsure.” `EvidenceGapAssessor` requires eligible partial evidence and a closed gap type. Reviewed clarification attribution remains separate from handbook citations, and the active handbook remains the policy authority.

## Certificate flow

```mermaid
flowchart TD
    Begin["Open Certificate Check"] --> Explain["Show local completeness-only boundary"]
    Explain --> Ack{"Acknowledged?"}
    Ack -- No --> Stop["No file processing"]
    Ack -- Yes --> Gate["Type, size, pages, structure, and active-content gates"]
    Gate --> Rejected{"Upload accepted?"}
    Rejected -- No --> NoResult["Upload Rejection; no result row"]
    Rejected -- Yes --> Extract["Local PDF text extraction or image OCR"]
    Extract --> Parse["Deterministic labelled-field parser"]
    Parse --> Outcome{"Outcome"}
    Outcome -- Complete --> SafeResult["Persist safe result metadata only"]
    Outcome -- Incomplete --> SafeResult
    Outcome -- Retryable --> Retry["One ephemeral retry token"]
    Retry --> RetryOutcome{"Retry succeeds?"}
    RetryOutcome -- Yes --> SafeResult
    RetryOutcome -- No --> Human["Needs Human Review plus blank manual template"]
    Human --> SafeResult
    SafeResult --> Share["Explicit share, revoke, or delete"]
```

File bytes, filenames, MIME details, extracted text, diagnosis, field values, confidence maps, and document fingerprints are not part of public history. The installation fingerprint key is stored outside SQLite with restrictive permissions. A `Complete` result is only a local structural completeness result; it is not authenticity, medical assessment, approval, or submission.

## Protected telemetry topology

```mermaid
flowchart LR
    Operation["UI/API operation"] --> Sanitize["Schema-v2 allowlist and v1 sanitizer"]
    Sanitize --> JSONL["Local bounded JSONL"]
    JSONL --> Shipper["Batch shipper: quarantine and partial retry"]
    Shipper -->|"authenticated batch"| Relay["Separate relay: event-ID idempotency"]
    Relay --> MLflow["Separate MLflow server and fixed experiments"]
    Relay -. "partial acknowledgement" .-> Shipper
```

The telemetry side channel never changes a product outcome. Event IDs are random and retry-stable. Only closed route, operation, outcome, count, latency, and experiment values are accepted; Hire identifiers, conversation text, policy text, certificate content, extracted values, diagnosis, filenames, fingerprints, and raw errors are denied. Local retention is bounded to seven days and 100 MB.

## Deployment boundary

The Docker image is Python 3.12 Linux, runs as non-root UID 10001, includes Tesseract English, and persists `/app/data` for SQLite and the separate installation key. The container smoke starts both Streamlit and FastAPI, checks their health, replays the six-turn payroll/context/escalation regression with zero wrong-topic citations, and proves a synthetic `Complete` certificate result. Nager is isolated from health; all private Hire, conversation, policy, document, OCR, and medical data remain local.
