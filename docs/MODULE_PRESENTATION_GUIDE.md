# AISHA Module Presentation Guide

Prepare a 10–15 minute core demo including Q&A. Keep optional material ready to extend to 15–20 minutes only if the instructor confirms the longer slot.

Open with the boundary: “AISHA is a fictional educational capstone for Payroll, Resource Access, and HR Policies. It is not affiliated with or endorsed by BDO Unibank, contains no real employee data, and is support—not surveillance.”

## Rehearsal

```bash
uv sync
uv run pytest
uv run streamlit run app.py
uv run uvicorn stai.api:app --port 8000
```

Optional live-model/index rehearsal:

```bash
ollama pull llama3.1:8b qwen2.5:3b-instruct nomic-embed-text
uv run python -m stai.ingestion
```

Run the complete acceptance command before presenting: `uv run python -m stai.acceptance`. Reset only through **Demo controls → Full Demo Reset**; explain that this clears local product state and rotates the certificate key but does not claim to erase already-shipped bounded telemetry or external backups.

## Core flow (about 11 minutes)

### 1. Product and privacy — 45 seconds

Show Alyssa Reyes as the one fictional Hire and the three-topic boundary. Say that applicability comes from four HR-confirmed attributes: Role Key, Department Key, Employment Classification, and Work Site. Chat cannot overwrite them. Point to the visible disclaimer.

### 2. Prompt Engineering + Chroma RAG — 90 seconds — Johann Casio

Ask `What does PAY-001 say?`

Point out:

- P3 was selected from P1/P2/P3 by the frozen Locked gate, not by preference.
- The answer is one validated typed response.
- Each material claim maps to active, authoritative, applicable evidence.
- The citation is policy/version/page metadata, not a model-authored filename or snippet.

Then ask an unsupported question and show Abstention without a related citation. Do not claim the deterministic benchmark measures live-model accuracy.

### 3. Structured Outputs + Disambiguation — 75 seconds — Jose Miguel Espinosa

Show the four Policy Response shapes in OpenAPI or tests. Demonstrate `Does ACC-006 apply to me?` with Alyssa’s confirmed branch Work Site, then use the prepared unknown-Work-Site fixture/test. AISHA asks one focused question only when that missing fact can change applicability; it does not mutate the profile.

### 4. ReAct + External Tool — 90 seconds — Bon Aquino / Johann Casio

Explain the bounded loop: Active Handbook → search → deterministic applicability → validated output → optional route. Show the fake-model trace in `tests/test_agent_smoke.py` if Ollama is unavailable.

Run or display the genuine Nager evidence. State exactly `Based on Nager.` Explain that the tool calls only the Philippines endpoint for the simulated current/following year, sends no Hire or content data, and supplies calendar facts—not employment consequences. An outage uses cache/handbook/human fallback and never changes health.

### 5. Consent-first case and profile revision — 75 seconds — Bon Aquino

Ask for a human about PAY-001. Show the Escalation Offer’s route and privacy-safe summary, then show that HR has no case yet. Consent explicitly; the case appears. In HR User, close it with the expected resource version.

Create a one-attribute Work Site request, then approve or reject it from HR. Explain that approval creates a revision; conversation text never becomes profile authority.

### 6. Certificate Check and History — 2 minutes — Jose Miguel Espinosa / Bon Aquino

Open Certificate Check. Read the short boundary: local completeness only—not authenticity, approval, medical assessment, or submission. Acknowledge, upload the synthetic labelled PDF, and show `Complete`.

Point out:

- Policy/applicability and acknowledgement run before file processing.
- PDF/JPG/PNG, 10 MB, three-page, structural and active-content gates are deterministic.
- Text extraction/OCR is local; bytes, filename/MIME, extracted values, confidence, diagnosis, and fingerprint are not public or retained as history.
- Upload Rejection/Check Failure create no result.
- One retry may end in a result or Needs Human Review with an ephemeral blank Manual Field Summary; completed manual values never return to AISHA.

Open History, share the result, show it in HR, revoke, then delete. Say the original still belongs in the separate fictional Official HR Document Route.

### 7. API + Memory — 75 seconds — Bon Aquino

Open `/docs`. Show `/api/v1/health`, conversation creation with fixed simulated date, a message replay using the same Idempotency-Key, and History. Emphasize server-owned ordered history: clients cannot submit arbitrary prior turns. Show that `/chat` and unversioned `/health` are absent.

Explain safe `{data,meta}` and `{error,meta}` envelopes, configured CORS, Alyssa-only demo namespace, resource versions, cursor bounds, and privacy-safe errors.

### 8. LLMOps + Docker + acceptance — 90 seconds — Jose Miguel Espinosa / Johann Casio

Show one schema-v2 JSONL event: random event ID, closed event/route/operation/outcome, counts and timings, with no Hire ID or content. Explain JSONL → bounded shipper → authenticated relay → separate MLflow and event-ID retry idempotency.

Show `evaluation/results/v1.1/acceptance.json` and the Docker smoke. The Linux image runs as UID 10001, installs Tesseract English, uses `/app/data`, and proves Streamlit health, `/api/v1/health`, the six-turn payroll/context/escalation regression with zero wrong-topic citations, and a synthetic Complete certificate result.

Finish with P3 Locked CSS and zero hard failures, followed immediately by the limitation: synthetic deterministic contract evidence, not production or real BDO validation.

## Accessibility walkthrough

Rehearse once at 320 CSS pixels and once on desktop:

1. Navigate role and destination controls using the keyboard.
2. Confirm visible focus and that app buttons provide at least 44-pixel targets.
3. Confirm no horizontal page overflow.
4. Read statuses without relying on color: Applies/Does Not Apply/Needs Clarification, result status, share state, and empty-state text.
5. Trigger a dynamic status and confirm the live/status region is announced by a screen reader.
6. Verify HR receives chat text only through the explicitly consented Case Thread, and never receives unrelated conversations, certificate content, or OCR/extracted values.

## Named ownership and Q&A

- Johann Casio: Prompt Engineering, Chroma RAG, External Tool Use, Dockerization.
- Jose Miguel Espinosa: Structured Outputs, Disambiguation, Guardrails, LLMOps Monitoring.
- Bon Aquino: Memory, ReAct Agent, Chat UI, API Endpoint.

Likely questions:

**Why not SQL Agent?** Chroma RAG is the selected retrieval module. SQLite operations are handwritten deterministic repository methods; no LLM generates SQL. SQL Agent is explicitly unclaimed.

**Why does classifier failure fail open?** It avoids making a small model outage a product outage. The consequential schema, applicability, evidence, citation, consent, version, and medical gates still fail closed.

**Can HR read Alyssa’s chat or certificate?** HR cannot browse Policy Conversations. After explicit consent, the linked history and future parent messages are copied into that case's shared thread until resolution. Unrelated chats and all certificate/OCR content remain inaccessible; only currently shared safe Validation Result metadata is visible.

**Does Complete mean the certificate is valid?** No. It means required demo fields were deterministically present/consistent. AISHA does not authenticate, approve, diagnose, or submit.

**What does the benchmark prove?** It proves regression compliance for a frozen synthetic capstone contract. It does not prove live-model accuracy, statistical certainty, production readiness, or real BDO performance.
