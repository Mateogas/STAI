CREATE TABLE IF NOT EXISTS case_information_requests (
    request_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES escalation_cases(case_id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    requested_by_hr_user TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','answered','cancelled')),
    hire_response TEXT,
    asked_at_utc TEXT NOT NULL,
    answered_at_utc TEXT,
    resource_version INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_case_one_pending_information_request
    ON case_information_requests(case_id) WHERE status='pending';
CREATE INDEX IF NOT EXISTS idx_case_information_requests_case
    ON case_information_requests(case_id, asked_at_utc, request_id);

CREATE TABLE IF NOT EXISTS case_interaction_modes (
    case_id TEXT PRIMARY KEY REFERENCES escalation_cases(case_id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'mediated' CHECK(mode IN (
        'mediated','direct_offered','direct_consented'
    )),
    offered_by_hr_user TEXT,
    offered_at_utc TEXT,
    consented_at_utc TEXT,
    resource_version INTEGER NOT NULL DEFAULT 1
);

INSERT OR IGNORE INTO case_interaction_modes(case_id, mode)
SELECT case_id, 'mediated' FROM escalation_cases;
