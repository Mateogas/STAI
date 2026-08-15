# Implementation Plan — Work Left

## Goal

Move AISHA from **feature-complete with offline evidence** to a **fully live-gated final capstone release** without changing its locked three-topic scope, consent model, privacy boundaries, or telemetry topology.

No known core product feature is missing. The remaining required work is environment setup, live integration proof, and final acceptance closure.

## Definition of done

The release is done when all of the following are true:

- The main and MLflow relay test suites pass from the canonical `uv` commands.
- The required Ollama models are installed and reachable.
- A verified Chroma build is active in SQLite.
- `/api/v1/health` reports the live agent and active index as ready.
- The disposable-staging six-turn dialogue gate passes with zero wrong-topic citations.
- The non-root Docker/Linux container smoke reports `LINUX_CONTAINER_SMOKE=PASS`.
- The three pending module rows are supported by recorded live evidence and changed to `Met`.
- `uv run python -m stai.acceptance` runs without skip flags and writes `status: passed`.
- The final Git worktree is clean and the evidence commit is pushed.

## Required sequence

### 1. Restore canonical local tooling

Make `uv` available on the shell `PATH`, then synchronize both environments.

```bash
uv --version
uv sync
cd mlflow-relay && uv sync && cd ..
```

Completion criterion: `uv --version` succeeds and both lockfile-based environments synchronize without dependency drift.

### 2. Prepare the live Ollama runtime

Start Ollama and install the configured agent, guardrail, and embedding models.

```bash
ollama serve
ollama pull llama3.1:8b
ollama pull qwen2.5:3b-instruct
ollama pull nomic-embed-text
ollama list
```

If Ollama is hosted elsewhere, set `STAI_OLLAMA_BASE_URL` rather than changing code. Model names remain environment-overridable with the `STAI_` settings in `.env.example`.

Production also uses `STAI_AGENT_RECURSION_LIMIT=32`,
`STAI_AGENT_MODEL_CALL_LIMIT=6`, and `STAI_AGENT_CONTEXT_WINDOW=8192`. The
model-call limit is the user-facing ReAct research budget; the larger graph
recursion limit leaves room for middleware and tool nodes. These are defaults,
but deployments with an explicit environment allowlist should declare them.
Remove any legacy `STAI_AGENT_ENABLED` value: the agent is mandatory and the
setting no longer exists.

Completion criterion: all three configured models appear in `ollama list`, and the application readiness probe can reach the configured Ollama endpoint.

### 3. Build and activate the Chroma knowledge base

Generate/verify the handbook if needed, then run the immutable staging ingestion.

```bash
uv run python -m stai.ingestion
```

Do not manually point SQLite at a collection. Ingestion must build a hash-named staging collection, verify artifact integrity and page identities, then atomically switch the active pointer. A failure must leave any prior active build untouched.

Completion criterion: the SQLite active retrieval-build record is present, its collection exists under the configured Chroma directory, verification passes, and a known Payroll query returns only eligible Payroll evidence.

### 4. Prove live application readiness

Start the API and Streamlit app against the prepared local state.

```bash
uv run uvicorn stai.api:app --host 127.0.0.1 --port 8000
uv run streamlit run app.py
curl http://127.0.0.1:8000/api/v1/health
```

Exercise the canonical demo journeys: grounded PAY-001, unsupported abstention, ACC-006 clarification, evidence-gated payroll-route offer, explicit consent, HR resolution, resolved-thread memory, reviewed clarification reuse, attribute change, and certificate result share/revoke/delete.

Completion criterion: health returns HTTP 200 and truthfully reports the agent,
classifier, and active index as ready. HTTP 503 is a deployment blocker, not a
degraded-but-usable state. All displayed policy evidence is structured and
topic-correct; privacy and consent boundaries remain intact.

### 5. Run the disposable-staging dialogue gate

Use a disposable staging database because this command intentionally creates a fictional consented case.

```bash
uv run python deploy/predeploy_dialogue.py \
  --base-url https://STAGING_HOST \
  --allow-state-mutation
```

Completion criterion: the exact six-turn payroll regression produces three grounded Payroll results, an eligible Payroll Support offer, one explicit consented case, and zero non-PAY citations while health is `ready`.

### 6. Start Docker and prove the Linux image

Start Docker Desktop or another compatible Docker daemon, then run the image and container smoke.

```bash
docker info
docker build -t aisha-demo .
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v aisha-smoke:/app/data aisha-demo uv run python -m stai.ingestion
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v aisha-smoke:/app/data \
  aisha-demo uv run python deploy/container_smoke.py
docker volume rm aisha-smoke
```

On native Linux, `host.docker.internal` requires the `--add-host` mapping above
when Ollama runs on the Docker host. If Ollama runs elsewhere, pass
`-e STAI_OLLAMA_BASE_URL=http://OLLAMA_HOST:11434` instead. Keep Ollama on a
private deployment network.

Completion criterion: the image builds, runs as `aisha` UID 10001, the UI
liveness check succeeds, `/api/v1/health` returns ready, the dialogue regression
has zero wrong-topic citations, the synthetic certificate result is `Complete`,
and the output contains `LINUX_CONTAINER_SMOKE=PASS`. Do not use Streamlit's
`/_stcore/health` as the production dependency-readiness probe.

### 7. Run the complete verification set

```bash
uv run pytest
cd mlflow-relay && uv run pytest && cd ..
uv run python -m stai.evaluation
```

Completion criterion: all suites are green, P3 remains selected under the locked tie-break, Locked CSS remains at least 0.90, every component remains at least 0.85, and hard failures remain zero.

### 8. Close the three live module gates

After—not before—the live evidence exists, update `ContextKnowledgeBase/ModuleChecklist.md`:

- Chroma RAG: `Implemented / Live gate pending` -> `Met`.
- ReAct Agent: `Implemented / Live gate pending` -> `Met`.
- Dockerization: `Implemented / Live gate pending` -> `Met`.

Update `ContextKnowledgeBase/ProjectState.md` and any dated release evidence so they describe the verified runtime without overstating broader production readiness.

Completion criterion: each changed module row links to reproducible evidence that satisfies its existing pass criterion.

### 9. Generate the final integrated acceptance report

Run without any skip flags:

```bash
uv run python -m stai.acceptance
```

Completion criterion: `evaluation/results/v1.1/acceptance.json` records the offline suite, live Nager result, Docker smoke, zero pending claimed modules, and top-level `status: passed`.

### 10. Rehearse and release

Follow `docs/MODULE_PRESENTATION_GUIDE.md` at desktop and 320 CSS pixels. Confirm the visible disclaimer, three-topic scope, four outcome types, evidence identities, sharing notice, private certificate boundary, HR restrictions, and acceptance report.

Then review and publish the final evidence intentionally:

```bash
git status --short
git diff --check
git diff --stat
git add -A
git commit -m "chore: finalize AISHA live acceptance evidence"
git push origin main
```

Completion criterion: the demonstration follows the 10–15 minute core path, the committed report is reproducible, no secrets or runtime data are staged, the worktree is clean, and the remote branch contains the final evidence commit.

## Guardrails for remaining work

- Preserve exactly three topics and the one-fictional-Hire namespace.
- Keep the generated active handbook as policy authority.
- Keep chat separate from Hire Profile authority.
- Require eligible partial evidence and a material Evidence Gap before offering HR.
- Keep offer, sharing notice, explicit consent, and case creation as separate states.
- Keep Case Exceptions thread-scoped and reusable clarifications review-gated.
- Keep certificate processing local and history result-only.
- Preserve JSONL -> shipper -> authenticated relay -> separate MLflow; make only additive telemetry changes.
- Keep raw conversations, policy text, certificate data, OCR values, diagnoses, identifiers, and raw errors out of telemetry.
- Keep `/api/v1` as the only public integration surface.
- Keep SQL Agent explicitly unclaimed.

## Optional post-capstone work

These are productization tasks, not blockers for the educational release:

- Add real identity, authentication, authorization, and audited RBAC.
- Define legal/HR/medical governance and retention policy.
- Conduct user research and accessibility testing with representative users.
- Run a versioned live-model study with repeated trials and confidence analysis.
- Evaluate OCR across more scan qualities, languages, and host builds.
- Add production secret management, backups, restore drills, and incident response.
- Perform security, privacy, threat-model, and deployment reviews.
