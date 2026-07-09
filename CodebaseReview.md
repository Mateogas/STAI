# Codebase Review vs Specification.pdf

Review date: 2026-07-09 (pre-submission audit against the STAI100 Midterm
Capstone spec). Everything below was verified against the working tree, not
just the docs: the full pytest suite was run (86 tests, all passed, no Ollama
needed), the Docker image was built from scratch (`docker build` succeeded),
and the containerized REST API was smoke-tested (`GET /health` returned valid
JSON from inside the container).

## Verdict at a glance

| Spec requirement | Status | Evidence |
|---|---|---|
| >=8 modules in the checklist | **Pass (11 solid + 1 with caveat)** | See module count below |
| Agent accessible via REST API | **Pass** | `src/stai/api.py`: `GET /health`, `POST /chat` run the full guarded agent pipeline via `src/stai/service.py`; `tests/test_api.py`; verified live in the container |
| LLMOps monitoring (traces, latency, tokens, errors) | **Pass on substance, one gap** | `src/stai/observability.py` logs all four per turn, wired into both UI and API; but metrics are not *visible* in any UI (Finding 3) |
| Docker: documented build/run, single command | **Pass with caveat** | Build verified clean; run documented in `Dockerfile` header + README; but first-run KB ingestion needs a second command (Finding 4) |
| GitHub repo: README (overview, setup, diagram, ownership table), Dockerfile, inline comments | **Mostly pass, two real gaps** | Ownership table has no team-member names (Finding 1); write-up image assets are untracked (Finding 2) |
| Web UI | Pass | Streamlit `app.py`; `tests/test_app_boot.py` boots it headlessly |
| Technical write-up >=2,000 words | Pass | `docs/TECHNICAL_WRITEUP.md` is 3,562 words and covers all five required topics (business case, methodology, architecture, experiments, retrospective) |
| Working end-to-end agentic app | Pass | 86/86 tests green; live demo requires host Ollama with the three models pulled |

## Module count (requirement: >=8)

Solidly met, with code and tests: Prompt Engineering (evaluated via the
guardrail model ablation in `docs/EVALUATION.md`, satisfying the spec's
"counts only when iterated and evaluated" note), Structured Outputs,
Disambiguation, RAG, Memory, Guardrails, ReAct Agent, Chat UI, API Endpoint,
LLMOps Monitoring, Dockerization — **11 modules**.

Met with a caveat: **Tool Use** — five real agent tools exist, but the spec
wording is "integrate at least one *external* tool or API". All five tools are
internal (Chroma, SQLite). The local-first rationale is documented in
`docs/EVALUATION.md`; treat this as a Q&A defense point, not a checklist claim
(see Finding 6).

Not met and correctly not claimed: SQL Agent (the LLM never generates SQL;
state goes through handwritten repository methods).

Even under the strictest reading (Tool Use excluded), 11 >= 8. A 4-person team
can assign 2+ distinct modules each with room to spare; the suggested split
already exists in `ContextKnowledgeBase/ModuleChecklist.md`.

---

## Findings and recommendations (ordered by severity)

### 1. README "module ownership table" has no team-member owners — spec-explicit gap

**Problem.** The spec's submission checklist requires the README to include a
"module ownership table", and Section 3.2 makes clear ownership means *people*
("each member must own and be able to explain at least 2 modules"). The
README's "Module ownership and evidence" table maps modules to **code paths
and tests**, not to team members. `ContextKnowledgeBase/ModuleChecklist.md`
only has a placeholder split (Person A/B/C/D). This is the clearest concrete
miss against the five wary items.

**Recommendation.** Add an `Owner` column with real member names to the
README table (keep the code/test columns — they are a strength). Make sure the
assignment gives every member at least 2 modules and matches who will actually
answer Q&A on them at the presentation.

### 2. Write-up figures are untracked; deliverable changes are uncommitted

**Problem.** `docs/TECHNICAL_WRITEUP.md` embeds
`assets/aisha-system-architecture.png` and `assets/aisha-turn-flow.png`, but
`docs/assets/` is **untracked** — on GitHub both figures 404, and the write-up
(a graded deliverable) renders with broken images. Separately, `app.py` and
`docs/TECHNICAL_WRITEUP.md` carry uncommitted modifications. The GitHub repo
*is* the submission; the graded state is whatever is pushed.

**Recommendation.** `git add docs/assets`, commit the modified `app.py` and
write-up, and push. Before the deadline, do a fresh `git clone` into a scratch
directory and confirm the README and write-up render with images and that
`uv sync && uv run pytest` passes from the clean clone.

### 3. LLMOps: metrics are logged but not *visible*; no observability "tool"

**Problem.** Two related risks against "Log traces, latency, token usage, and
errors using an observability tool (e.g., MLFlow)":

- The substance is fully there — `observability.py` writes per-turn JSONL with
  route, models, estimated input/output tokens, `latency_ms`, `tools_used`
  (the trace), sources, guardrail category, and `error`, wired into both the
  Streamlit path (`app.py`) and the API path (`service.py` `TurnObserver`).
  But the spec's submission checklist says "traces, latency, token usage
  **visible**", and today the only way to see them is `Get-Content` /
  grep / pandas. Notably, `observability.read_runs()` already exists and is
  used by nothing in the UI.
- A strict grader may read "observability tool" as requiring an actual tool
  (MLflow, Langfuse, etc.) rather than a hand-rolled JSONL sink. The
  JSONL-over-MLflow rationale is well documented (module docstring, README,
  `docs/EVALUATION.md`), which makes this defensible — but it is the weakest
  of the five wary items after Finding 1.

**Recommendation.** Cheapest high-value fix: add a small "Ops" panel/tab to
the HR admin view in `app.py` that calls `read_runs()` and renders (a) a
runs table, (b) latency and token charts, (c) an error/refusal count. That
converts the requirement from "greppable" to "demonstrable on screen during
the live demo" with ~30 lines of Streamlit. If there is spare capacity,
an optional MLflow sink behind a `STAI_MLFLOW_URI` env var would close the
"tool" reading entirely (the module docstring already notes `log_turn` is a
one-function swap point), but do the in-UI panel first — it is what the
rubric's demo actually rewards. Keep the honest `est_*` token naming and be
ready to explain it in Q&A (Ollama via LangChain does not reliably report
usage).

### 4. Docker: functional demo is not truly single-command

**Problem.** "Dockerfile builds and runs cleanly with a single command" — the
build is one command (verified), and `docker run` starts the UI or API (also
verified: `/health` answered from inside the container). But a fresh container
has an **empty knowledge base** (`data/chroma/` is deliberately
`.dockerignore`d) until someone runs a second command
(`docker exec <container> uv run python -m stai.ingestion`), and RAG answers
need host Ollama regardless. A grader who runs exactly one command gets an app
whose KB queries return nothing.

**Recommendation.** Add a small entrypoint script that, on container start,
runs ingestion automatically when the Chroma collection is empty and Ollama is
reachable (fail soft with a clear log line when it is not), then launches the
CMD. Optionally add a `docker-compose.yml` that starts an `ollama/ollama`
service plus the app, giving graders a genuine one-command path
(`docker compose up`). If neither lands before the deadline, the current
documentation is at least explicit — call out the two-step first run verbally
in the demo, and note `kb_ready` in `/health` is the check.

### 5. Repo hygiene: tracked junk undermines the "clean code repository" criterion

**Problem.** Code Quality/Documentation/README is 10% of the grade and asks
for a *clean* repository. Currently tracked in git:

- `test.txt` — empty leftover file at repo root.
- `docs/~$AI_AISHA_Technical_Writeup.docx` — a Word *lock file* (temp artifact
  created while the .docx is open; should never be committed).
- `.render/` — ~16 build artifacts (per-page PNGs, draft and final PDFs) of
  the write-up render pipeline.
- `UIUXRedesignReference.zip` alongside the extracted
  `UIUXRedesignReference/` folder (duplicate content, currently also showing
  uncommitted modifications), plus untracked `UIUXRedesignReference/screenshots/`.

**Recommendation.** `git rm --cached` the lock file and `test.txt`; decide
whether `.render/` outputs belong in the repo (if the final PDF is a
deliverable, keep only `final.pdf` and drop the page PNGs/draft). Keep either
the zip or the extracted folder, not both. Add `~$*` and `.render/` (or the
dropped subset) to `.gitignore`. Total effort: minutes; it is the difference
between a repo that looks curated and one that looks dumped.

### 6. Tool Use module: "external tool or API" wording — presentation risk

**Problem.** The spec defines Tool Use as integrating "at least one *external*
tool or API (search, weather, calendar, etc.)". AISHA's five tools are
internal closures over Chroma/SQLite. The rationale (local-first, no real BDO
systems, privacy story) is genuinely good and documented — but if a grader
scores the module checklist literally, Tool Use may not count.

**Recommendation.** No code change required for compliance (the count is 11
without it). Either (a) do not claim Tool Use on the ownership table and
present the five tools under ReAct Agent, or (b) claim it with the documented
defense ready. If the team wants it airtight and has an hour: one genuinely
external tool that fits the story — e.g., a Philippine-holidays lookup for
"is my Day 30 check on a holiday?" via a public API with an offline JSON
fallback — would satisfy the letter of the spec without breaking the
local-first demo.

### 7. Minor: guardrail battery score inconsistency across docs

**Problem.** The qwen guardrail battery score is recorded as **14/15** in
`src/stai/config.py` but **15/15** in `.env.example` and `CLAUDE.md`;
`docs/EVALUATION.md` reports the discrepancy honestly ("14-15/15, rerun on
your own hardware"). Small, but experiment numbers that disagree across files
are exactly what a grader probing "evidence-based testing" will poke at.

**Recommendation.** Rerun the 15-case battery once on the demo machine,
record the single number everywhere, and note the date/hardware in
`docs/EVALUATION.md`.

### 8. Reminder: deliverables that live outside the repo

Not code findings, but spec items nothing in this repo can satisfy:
presentation slides (required, submitted separately), the live demo fallback
(spec explicitly suggests preparing a screen recording and disclosing it
upfront), and every member being ready to defend their owned modules. The
demo machine needs Ollama running with `llama3.1:8b`, `qwen2.5:3b-instruct`,
and `nomic-embed-text` pulled, plus `uv run python -m stai.ingestion` run
beforehand — worth a dry run on the actual presentation hardware.

---

## What was verified by execution (not just reading)

| Check | Result |
|---|---|
| `uv run pytest` (full suite, no Ollama) | 86 tests collected, exit code 0 (all passed) |
| `docker build -t aisha-demo-review .` | Built cleanly from the current working tree |
| `docker run` + `curl /health` on the built image | `{"status":"ok","kb_ready":false,"employees":3,...}` — API serves; `kb_ready:false` is expected pre-ingestion (see Finding 4) |
| Write-up word count | `docs/TECHNICAL_WRITEUP.md` = 3,562 words (>=2,000) |
| Observability wiring | `TurnObserver` in `service.py` (API route); `log_turn` at three call sites in `app.py` (Streamlit route) |
| GitHub remote | `https://github.com/Mateogas/STAI.git` |
