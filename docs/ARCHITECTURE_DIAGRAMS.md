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
        Case["Consented escalation case"]
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
    Allowed -- Yes --> Version["Get active handbook identity"]
    Version --> Search["Hybrid search and eligibility gates"]
    Search --> Found{"Eligible evidence?"}
    Found -- No --> Abstain["Abstention; no unrelated citation"]
    Found -- Yes --> Applicable{"All constraining attributes known?"}
    Applicable -- No --> Clarify["One focused clarification; no mutation"]
    Applicable -- Yes --> Claim["Generate candidate typed result"]
    Claim --> Validate["Schema, applicability, claim, and citation validation"]
    Validate --> Valid{"Valid?"}
    Valid -- No --> SafeAbstain["Fail-closed typed abstention"]
    Valid -- Yes --> Persist["Persist ordered safe outcome and evidence identity"]
    Persist --> Render["Render identical UI/API semantics"]
    Render --> Offer{"Human support requested or useful?"}
    Offer -- Yes --> OfferOnly["Create offer; case only after explicit consent"]
```

Evidence exposed to users is structured identity—policy ID, revision, handbook version, page, and artifact hashes—not stored raw snippets or model-authored filename citations. Conversation history is server owned and ordered. It informs continuity but never becomes authority for Hire Profile attributes.

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

The Docker image is Python 3.12 Linux, runs as non-root UID 10001, includes Tesseract English, and persists `/app/data` for SQLite and the separate installation key. The container smoke starts both Streamlit and FastAPI, checks their health, proves a PAY-001 policy answer, and proves a synthetic `Complete` certificate result. Nager is the only product network dependency and is isolated from health; all private Hire, conversation, policy, document, OCR, and medical data remain local.
