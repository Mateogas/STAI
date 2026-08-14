CREATE TABLE IF NOT EXISTS validation_result_agent_runs (
    validation_id TEXT PRIMARY KEY REFERENCES validation_results(validation_id) ON DELETE CASCADE,
    execution_mode TEXT NOT NULL CHECK(execution_mode IN ('react','deterministic_degraded'))
);

CREATE TABLE IF NOT EXISTS validation_result_agent_actions (
    validation_id TEXT NOT NULL REFERENCES validation_results(validation_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN (
        'confirm_certificate_policy',
        'run_local_ocr_validation',
        'validate_certificate_result',
        'persist_safe_result'
    )),
    PRIMARY KEY(validation_id, ordinal)
);
