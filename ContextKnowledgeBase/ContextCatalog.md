# AISHA Context Catalog

## Minimum handoff

Read in order:

1. `README.md`
2. `AISHAStorySpine.md`
3. `ProjectState.md`

Then select one route:

| Work route | Read next | Primary implementation |
|---|---|---|
| Policy domain, applicability, consent | `OpenQuestions.md` | `models.py`, `policy.py`, `service.py`, `state.py` |
| Handbook and retrieval | `docs/ARCHITECTURE_DIAGRAMS.md`, `docs/EVALUATION.md` | `handbook.py`, `ingestion.py`, `retriever.py`, `guardrails.py` |
| Certificate Check | `AISHAStorySpine.md`, medical sections of `docs/TECHNICAL_WRITEUP.md` | `medical.py`, `state.py`, UI/API validation routes |
| UI/UX | `UIUXBrief.md`, `docs/MODULE_PRESENTATION_GUIDE.md` | `app.py`, `tests/test_ui_contract.py` |
| API | `README.md` API section | `api.py`, `tests/test_api.py`, `tests/test_api_privacy.py` |
| Telemetry/LLMOps | `docs/EVALUATION.md`, ADR 0001 | `observability.py`, `log_shipper.py`, `mlflow-relay/` |
| Benchmark and acceptance | `ImplementationPlan.md`, `ModuleChecklist.md` | `evaluation/`, `acceptance.py`, Docker smoke |

## Locked boundaries

- Exactly three product topics: Payroll, Resource Access, HR Policies.
- One fictional Hire namespace: Alyssa Reyes.
- Four HR-confirmed applicability attributes; chat is never profile authority.
- Structured policy citations use policy/version/page/artifact identity.
- Escalation is offer-before-case and requires explicit consent.
- Escalation requires a deterministic Evidence Gap backed by eligible partial policy evidence; omissions, outages, unsupported topics, and bare human requests do not qualify.
- Case Resolution Memory is thread-scoped. Only a reviewed Published Policy Clarification may supplement later answers, and policy changes require a new handbook revision.
- Certificate Check is local completeness only with result-only history.
- HR has no direct policy-conversation read path. Explicit case consent copies the linked parent history and mirrors future parent messages into the HR-visible Case Thread until resolution; unrelated conversations and certificate content remain inaccessible.
- Public integration is typed `/api/v1` only.
- Telemetry is closed metadata through JSONL → shipper → authenticated relay → separate MLflow.
- Chroma RAG is claimed; SQL Agent is explicitly unclaimed.

## Verification

```bash
uv run pytest
cd mlflow-relay && uv run pytest
uv run python -m stai.acceptance
```

Historical migration wording may remain in `Changelog.md` or design records only. It must not reappear in production code, current user documentation, public schemas, seeded runtime data, or UI labels.
