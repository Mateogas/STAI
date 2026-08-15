# AISHA — AI Support for Hires and Associates

AISHA is a local-first agentic onboarding-policy assistant for a fictionalized BDO educational capstone. It is not affiliated with, endorsed by, or representative of BDO Unibank. It contains no real BDO employee data and has no access to BDO systems.

The shipped demo supports one fictional Hire, Alyssa Reyes, across exactly three topics: Payroll, Resource Access, and HR Policies. Its goal is reliable, privacy-conscious onboarding guidance—not generic HR Q&A and not employee surveillance.

## What is implemented

- Four typed policy outcomes plus a separate consented Escalation Confirmation workflow result.
- Deterministic Evidence Gap assessment: HR is offered only for a partially supported policy question, never for a bare human request, unsupported subject, or index outage.
- A deterministic 108-page AISHA Handbook v1.1 with immutable page records, a hashed authoritative-public-source register, and policy/version/page citations.
- Hybrid Chroma retrieval with active-edition, authority, applicability, integrity, activation, and rollback gates.
- A confirmed four-attribute Hire Profile; chat never changes applicability.
- A shared `PolicyTurnEngine` with typed Agent Plans, bounded restart-safe context, semantic policy catalogs, payroll/HR sub-intents, consented child Case Threads, structured Case Resolution Memory, reviewed clarification reuse, and result-only certificate History in normalized SQLite.
- Local PDF/image medical-certificate completeness checking with policy-before-file access, Tesseract OCR, deterministic rules, one retry, and private-by-default results.
- A bounded Philippines-only Nager.Holidays tool with exact `Based on Nager.` attribution, seven-day cache, retry, validation, circuit breaking, and safe fallbacks.
- Streamlit New Hire destinations—Ask AISHA, Certificate Check, History—with reopenable chats and nested HR ticket threads, plus a separate HR User workspace.
- A typed `/api/v1` contract with safe envelopes/errors, request IDs, fixed simulated dates, configured CORS, idempotency, resource versions, and cursor pagination.
- Schema-v2 operational telemetry through local JSONL → rotating shipper → authenticated FastAPI relay → separate MLflow server.
- A frozen 60-case Composite Safety Benchmark and non-root Linux container smoke.

## Local setup

Python 3.12 and [`uv`](https://docs.astral.sh/uv/) are required. Logic and API
tests use model fakes. The Streamlit interaction tests also fake the chat model,
but they use the real local database; when it points to an active Chroma build,
the configured Ollama embedding endpoint must be running.

```bash
uv sync
uv run pytest
uv run streamlit run app.py
uv run uvicorn stai.api:app --host 127.0.0.1 --port 8000
```

The following model/index setup is optional only for offline tests. It is
required for every deployed policy conversation:

```bash
ollama pull llama3.1:8b
ollama pull qwen2.5:3b-instruct
ollama pull nomic-embed-text
uv run python -m stai.ingestion
```

Ingestion builds a version/hash-named staging collection from `handbook/dist/rag-pages.jsonl`, verifies it, and atomically changes the SQLite active pointer. It never resets an active collection in place. A failed or partial build leaves the current pointer untouched.

Both Streamlit and `/api/v1` call the same turn engine. Every supported turn
enters the ReAct loop with bounded conversation context. ReAct resolves intent,
revises retrieval, reads policy bundles, and returns a typed plan and response
draft. Deterministic code then validates handbook/citation identity,
applicability, exact claim support, privacy, and consent before persistence or
mutation. There is no local answer fallback; missing model or index readiness
causes `/api/v1/health` to return `503`.

## Streamlit journeys

Run `uv run streamlit run app.py`, then use:

1. **Ask AISHA** — create or reopen a chat, ask `What does PAY-001 say?`, and inspect the metadata-only Evidence area.
2. **Clarification** — demonstrate ACC-006 with a missing or disputed Work Site and show one focused question.
3. **Certificate Check** — acknowledge the local result-only notice, upload one synthetic PDF/PNG/JPEG, and inspect the deterministic result.
4. **History** — share a Validation Result, revoke it, and delete it. Original files and extracted text never appear.
5. **Evidence-gated HR ticket** — ask `Where is the official payroll route?`, inspect the supported PAY-003 portion and material route gap, then review the explicit sharing notice and create the case. A bare `Connect me with HR` without a qualifying question does not create an offer.
6. **Resolution memory** — resolve from HR with a type and scope, then ask AISHA a related follow-up inside the resolved child thread.
7. **Reviewed reuse** — propose a non-case-only Policy Clarification, approve it in the demo review, and see it supplement a later handbook-grounded answer with separate attribution.
8. **HR User** — ask one missing detail through AISHA, save an HR-only note, resolve the case, and show direct human conversation only after a separate Hire consent. Also show currently shared Validation Results and pending Attribute Change Requests.

The layout is verified at 320–390 CSS pixels, uses visible keyboard focus and non-color state text, provides 44-pixel app controls, and announces dynamic status through accessible live/status regions.

## REST API

OpenAPI is at `http://localhost:8000/docs`. The only health path is:

```bash
curl http://localhost:8000/api/v1/health
```

Create a fixed-date Policy Conversation and send a turn:

```bash
curl -X POST http://localhost:8000/api/v1/hires/emp-alyssa/conversations \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-conversation' \
  -d '{"simulated_date":"2026-08-10"}'

curl -X POST http://localhost:8000/api/v1/hires/emp-alyssa/conversations/CONVERSATION_ID/messages \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-turn' \
  -d '{"message":"What does PAY-001 say?"}'
```

Every success uses `{data, meta}`; every error uses `{error, meta}`. Side effects require `Idempotency-Key`: the same key/input replays the semantic result across restarts, while different input returns `409`. Mutable resources use expected versions. Lists use newest-first cursors with a default of 20 and maximum of 100.

Case endpoints expose the same nested workflow used by Streamlit. HR reads the copied Case Thread, not the underlying Policy Conversation store, and uses a structured information-request endpoint instead of joining the thread by default. AISHA asks the Hire and links the answer back to the case. Direct HR messages require a separate offer and Hire-consent endpoint. Consent backfills the parent history and mirrors future parent messages while the case is open; resolution stops mirroring. Resolved Hire messages use Case Resolution Memory. `/clarification-review/{approve|reject}` controls broader reuse with its own optimistic version.

Public responses never contain raw exceptions, model names, internal paths, snippets, scores, hashes, collection identities, certificate bytes, filenames/MIME metadata, OCR or extracted values, confidence data, diagnoses, or Document Fingerprints. Detected medical content is rejected before ordinary chat persistence.

## Certificate boundary

Certificate Check is a synchronous local completeness check under fictional policy HRP-004. It is not authenticity verification, HR approval, medical assessment, diagnosis, or document submission.

- Accepted: one PDF, PNG, or JPEG; at most 10 MB; PDF at most three pages.
- Active/embedded PDF content, corrupt structure, MIME/extension mismatch, and oversized media fail before extraction.
- Text-layer PDF extraction and local Tesseract OCR remain on the demo machine.
- Only safe result status/codes, policy citation, profile revision, attempts, timestamps, share state, and version persist.
- Upload Rejection and Check Failure create no Validation Result or fingerprint.
- One replacement retry is available for low-confidence or unrecognized-date extraction.
- The original document must be submitted separately through the fictional Official HR Document Route; AISHA does not upload or confirm submission.

## Nager.Holidays

`lookup_public_holidays(year)` calls only `https://date.nager.at/api/v3/PublicHolidays/{year}/PH`. It accepts only the simulated current/following Asia/Manila year. The tool sends no Hire, conversation, policy, document, OCR, or medical content. Calendar facts are attributed exactly `Based on Nager.` and never decide employment consequences without cited handbook policy. `/api/v1/health` never calls Nager, and an outage cannot make AISHA unhealthy.

## Telemetry and MLflow

New records use schema v2 and a random delivery-only event ID. They contain closed operation/outcome/error metadata, bounded counts, booleans, stage timings, and release identifiers. They do not contain identities or content. Schema-v1 rows pass through one sanitizing mapper; malformed or unknown-version lines are quarantined individually without copying their content.

```bash
uv run python -m stai.log_shipper
cd mlflow-relay && uv run pytest
```

The shipper atomically rotates JSONL, retains retryable batches for at most seven days/100 MB, sends bounded batches to the authenticated relay, and deletes only acknowledged/already-present event IDs. The relay applies the same allowlists, routes closed event kinds to four fixed MLflow experiments, and suppresses response-loss duplicates. MLflow operation runs have a documented 30-day retention boundary; a Full Demo Reset does not claim to delete already-shipped telemetry or external backups.

## Benchmark and final acceptance

The versioned benchmark contains 60 synthetic cases: 18 policy/applicability, 12 retrieval/index, 6 dialogue/safety, 8 Nager, and 16 medical; 40 are Calibration and 20 Locked Acceptance. Components G/R/A/D/M/X form a weighted harmonic Composite Safety Score. Passing requires CSS ≥ 0.90, every component ≥ 0.85, and zero safety-critical failures.

```bash
uv run python -m stai.evaluation
uv run python -m stai.acceptance
```

The frozen prompt benchmark remains in `evaluation/results/v1.0/`. The integrated v1.1 acceptance report adds the deployed six-turn payroll regression, restart-safe context, wrong-topic citation gate, and offer-to-consent progression at `evaluation/results/v1.1/acceptance.json`. These offline checks do not claim live-model, statistical, production, or real BDO performance.

## Docker and Linux/Proxmox

```bash
docker build -t aisha-demo .
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v aisha-data:/app/data aisha-demo uv run python -m stai.ingestion
docker run --rm -p 8501:8501 --add-host=host.docker.internal:host-gateway \
  -v aisha-data:/app/data aisha-demo
docker run --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway \
  -v aisha-data:/app/data \
  aisha-demo uv run uvicorn stai.api:app --host 0.0.0.0 --port 8000
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v aisha-smoke:/app/data \
  aisha-demo uv run python deploy/container_smoke.py
```

The commands above assume Ollama runs on the Linux Docker host. If it runs
elsewhere, replace the image default with
`-e STAI_OLLAMA_BASE_URL=http://OLLAMA_HOST:11434`. Keep Ollama private to the
deployment network; do not expose port 11434 publicly.

Before deployment, run the dialogue gate against a disposable staging database
whose health status is `ready`:

```bash
uv run python deploy/predeploy_dialogue.py \
  --base-url https://STAGING_HOST --allow-state-mutation
```

The staging gate intentionally creates one fictional consented case and must
not be run against a persistent production database.

The image runs as `aisha` UID 10001, includes Tesseract English, PyMuPDF,
Pillow, multipart support, and persists SQLite/Chroma/key state under
`/app/data`. Run ingestion against that same persistent volume before starting
a newly provisioned deployment. Ollama is intentionally external; do not place
SQLite or Chroma on NFS/SMB or behind multiple replicas. A single VM/LXC
instance with a local persistent volume is the supported demo topology.

### Production upgrade checklist

1. Pull `main`, rebuild the image or run `uv sync --frozen`, and preserve a
   backup/snapshot of the production `/app/data` volume.
2. Pull all required models on the Ollama host:
   `llama3.1:8b`, `qwen2.5:3b-instruct`, and `nomic-embed-text`.
3. Set `STAI_OLLAMA_BASE_URL` to an address reachable from the application.
   `STAI_AGENT_RECURSION_LIMIT=32`, `STAI_AGENT_MODEL_CALL_LIMIT=6`, and
   `STAI_AGENT_CONTEXT_WINDOW=8192` are the defaults; declare them explicitly
   if production uses an environment allowlist. Remove obsolete
   `STAI_AGENT_ENABLED` configuration.
4. Run `uv run python -m stai.ingestion` against the production persistent
   volume. The command stages and verifies the collection before atomically
   changing the active pointer.
5. Start both surfaces if both are deployed. Streamlit's `/_stcore/health`
   checks only the UI process; it does not prove that Ollama or Chroma is ready.
6. Configure the deployment readiness probe against
   `GET /api/v1/health` on the FastAPI process. Production is ready only when it
   returns HTTP 200 with `data.status == "ready"`; HTTP 503 means a required
   model, embedding model, or active Chroma build is unavailable.

No SQLite schema migration or new secret is required for this ReAct refactor.

## Module scope

The canonical evidence and ownership matrix is [`ContextKnowledgeBase/ModuleChecklist.md`](ContextKnowledgeBase/ModuleChecklist.md). The 12 claimed modules are Prompt Engineering, Structured Outputs, Disambiguation, Chroma RAG, Memory, Guardrails, ReAct Agent, External Tool Use, Chat UI, API Endpoint, LLMOps Monitoring, and Dockerization. SQL Agent is explicitly unclaimed because Chroma RAG is the selected retrieval module.

Named ownership is balanced across Johann Casio, Jose Miguel Espinosa, and Bon Aquino, with at least two claimed modules per team member. See [`docs/MODULE_PRESENTATION_GUIDE.md`](docs/MODULE_PRESENTATION_GUIDE.md) for the 10–15 minute core demo plus optional extension and [`docs/EVALUATION.md`](docs/EVALUATION.md) for the complete gate trace and limitations.
