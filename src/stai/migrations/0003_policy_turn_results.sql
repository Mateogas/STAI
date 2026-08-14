CREATE TABLE IF NOT EXISTS policy_turn_results (
    message_id TEXT PRIMARY KEY REFERENCES policy_messages(message_id) ON DELETE CASCADE,
    result_type TEXT NOT NULL,
    dialogue_act TEXT NOT NULL,
    resolved_topic TEXT,
    referenced_message_id TEXT REFERENCES policy_messages(message_id) ON DELETE SET NULL,
    execution_mode TEXT NOT NULL CHECK(execution_mode IN ('agent','deterministic','degraded')),
    safe_payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_policy_turn_results_topic
    ON policy_turn_results(resolved_topic, message_id);
