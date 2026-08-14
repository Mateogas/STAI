CREATE TABLE IF NOT EXISTS case_threads (
    case_id TEXT PRIMARY KEY REFERENCES escalation_cases(case_id) ON DELETE CASCADE,
    parent_conversation_id TEXT REFERENCES policy_conversations(conversation_id) ON DELETE SET NULL,
    originating_message_id TEXT,
    sharing_active INTEGER NOT NULL DEFAULT 1 CHECK(sharing_active IN (0,1)),
    workflow_state TEXT NOT NULL DEFAULT 'waiting_for_hr'
        CHECK(workflow_state IN ('waiting_for_hr','waiting_for_hire','in_progress','resolved')),
    assigned_hr_user TEXT,
    resolution_summary TEXT,
    resolved_at_utc TEXT,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_messages (
    case_message_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES escalation_cases(case_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    actor_role TEXT NOT NULL CHECK(actor_role IN ('hire','aisha','hr','system')),
    actor_id TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'shared' CHECK(visibility IN ('shared','hr_internal')),
    text TEXT NOT NULL,
    source_policy_message_id TEXT,
    created_at_utc TEXT NOT NULL,
    UNIQUE(case_id, ordinal),
    UNIQUE(case_id, source_policy_message_id)
);

CREATE TABLE IF NOT EXISTS case_events (
    case_event_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES escalation_cases(case_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor_role TEXT NOT NULL CHECK(actor_role IN ('hire','aisha','hr','system')),
    actor_id TEXT NOT NULL,
    safe_payload_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_notifications (
    notification_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES escalation_cases(case_id) ON DELETE CASCADE,
    audience_role TEXT NOT NULL CHECK(audience_role IN ('hire','hr')),
    recipient_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('case_created','parent_message','case_reply','case_resolved')),
    text TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    read_at_utc TEXT
);

CREATE INDEX IF NOT EXISTS idx_case_threads_parent
    ON case_threads(parent_conversation_id, sharing_active, case_id);
CREATE INDEX IF NOT EXISTS idx_case_messages_case
    ON case_messages(case_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_case_events_case
    ON case_events(case_id, created_at_utc, case_event_id);
CREATE INDEX IF NOT EXISTS idx_case_notifications_recipient
    ON case_notifications(audience_role, recipient_id, read_at_utc, created_at_utc DESC);

INSERT OR IGNORE INTO case_threads (
    case_id, parent_conversation_id, originating_message_id, sharing_active,
    workflow_state, assigned_hr_user, resolution_summary, resolved_at_utc, created_at_utc
)
SELECT
    case_id, NULL, NULL, CASE WHEN status='open' THEN 1 ELSE 0 END,
    CASE WHEN status='open' THEN 'waiting_for_hr' ELSE 'resolved' END,
    closing_hr_user, NULL, closed_at_utc, created_at_utc
FROM escalation_cases;
