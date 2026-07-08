# Module Checklist

This file maps the course module checklist to the current codebase.

## Summary

Narrative status:

- Front-facing product should be AISHA: AI Support for Hires and Associates.
- Demo setting should be fictionalized BDO with the required educational
  disclaimer from `AISHAStorySpine.md`.
- Existing implementation may still contain Meridian/Maya/Meri until the BDO
  synthetic-data slice is completed. Treat those as stale demo data, not the
  target story.
- The main business value is faster productivity/time-to-ramp, supported by
  onboarding/ramp state, trend signals, and HR support cards.

| Module | Current status | Evidence | Next action |
|---|---|---|---|
| Prompt Engineering | Met | Persona system prompt in `agent.py`; few-shot guardrail classifier in `guardrails.py`; documented guardrail model comparison. | Keep, then document in evaluation/write-up. |
| Structured Outputs | Met | Pydantic models parse guardrail and pulse JSON outputs. | Keep. |
| Disambiguation | Partial | Prompt says to ask one clarifying question; fuzzy matching exists for tasks/people. | Add deterministic ambiguity detection before mutation. |
| RAG | Met | `ingestion.py`, `retriever.py`, Chroma, HR docs, source formatting. | Keep; add retrieval eval examples. |
| Memory | Partial | Streamlit session memory plus SQLite domain state. No persistent chat messages. | Add `chat_messages` table and repo methods if claiming long-term memory. |
| Guardrails | Met | Input topic/injection classifier; citation enforcement; output PII redaction. | Clarify PII is output-side only. |
| ReAct Agent | Met | LangChain/LangGraph agent loop with tools. | Keep. |
| SQL Agent | Not met | SQLite is used through handwritten repository methods; LLM does not generate SQL. | Probably do not chase unless team needs another module. |
| Tool Use | Mostly met, caveat | Five internal tools exist. | Decide if external API is required by instructor. If yes, add a small external integration or document internal tool rationale. |
| Chat UI | Met | Streamlit chat and HR dashboard in `app.py`. | Redesign flow for usability. |
| API Endpoint | Not met | No FastAPI/Flask/Uvicorn. | Implement REST endpoint. |
| LLMOps Monitoring | Not met | No MLflow/LangSmith/tracing dependency. | Implement MLflow/basic observability. |
| Dockerization | Not met | No Dockerfile. | Add Dockerfile and README instructions. |

## Hard requirements from Specification.pdf

The spec explicitly requires:

- web UI,
- REST API endpoint,
- basic LLMOps monitoring,
- Dockerfile,
- technical write-up,
- experiment findings,
- README with setup and architecture,
- live demo.

Therefore the highest-priority remaining engineering tasks are:

1. API endpoint.
2. LLMOps monitoring.
3. Dockerization.
4. Evaluation/write-up artifact.

## Defensible current claims

These can be claimed now with code evidence:

- RAG with citations.
- Guardrails.
- Structured outputs.
- ReAct/tool-using agent.
- Streamlit chat UI.
- SQLite-backed onboarding state.
- Pulse/risk dashboard.

AISHA-specific claims once the rebrand slice is complete:

- Role-based onboarding and ramp support for Alyssa Reyes, a fictionalized BDO
  Management Trainee / Branch Banking Associate.
- Day 30 readiness framing instead of a 30-60-90 onboarding story.
- Support-card framing for HR: enough signal to help, not enough detail to
  police.
- Educational/fictional BDO disclaimer throughout demo/docs.

These should be claimed carefully:

- Memory: currently short-term session memory and persistent domain memory, not
  persistent conversation memory.
- Disambiguation: currently weak/implicit, not a robust module.
- Tool Use: strong internal tool use, but not a third-party external API.

## Recommended module ownership split

If the team needs module ownership for presentation:

- Person A: RAG, prompt engineering, citations.
- Person B: guardrails, structured outputs, disambiguation.
- Person C: memory, tools, ReAct agent.
- Person D if present: API, Docker, LLMOps, evaluation.

If only three people are presenting, assign API/Docker/LLMOps across the same
people as deployment and reliability responsibilities.
