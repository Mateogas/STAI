# Preserve the existing MLflow observability pipeline

The onboarding refactor will retain the current local JSONL observer, tested
batch shipper, authenticated FastAPI relay, and separate MLflow server topology
unless a verified incompatibility requires an additive change. This deployment
required dedicated setup, already satisfies the LLMOps requirement without
adding MLflow to the demo application's dependency path, and keeps monitoring
failures from breaking chat turns. New onboarding metrics may extend the
existing record and relay mapping, but raw message text, uploaded documents,
OCR text, diagnoses, and other medical content must never be logged.
