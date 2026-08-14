CREATE TABLE IF NOT EXISTS escalation_offer_evidence_gaps (
    offer_id TEXT PRIMARY KEY REFERENCES escalation_offers(offer_id) ON DELETE CASCADE,
    gap_kind TEXT NOT NULL CHECK(gap_kind IN (
        'missing_procedure','exception_unclear','policy_conflict','route_unclear'
    )),
    safe_known_text TEXT NOT NULL,
    unresolved_question TEXT NOT NULL,
    eligibility_reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_evidence_gaps (
    case_id TEXT PRIMARY KEY REFERENCES escalation_cases(case_id) ON DELETE CASCADE,
    gap_kind TEXT NOT NULL CHECK(gap_kind IN (
        'missing_procedure','exception_unclear','policy_conflict','route_unclear'
    )),
    safe_known_text TEXT NOT NULL,
    unresolved_question TEXT NOT NULL,
    eligibility_reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_resolutions (
    resolution_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL UNIQUE REFERENCES escalation_cases(case_id) ON DELETE CASCADE,
    resolution_type TEXT NOT NULL CHECK(resolution_type IN (
        'policy_clarification','case_exception','policy_amendment_candidate','unable_to_resolve'
    )),
    resolution_scope TEXT NOT NULL CHECK(resolution_scope IN (
        'case_only','hire','organization'
    )),
    answer TEXT NOT NULL,
    reuse_status TEXT NOT NULL CHECK(reuse_status IN (
        'thread_only','pending_review','approved','rejected','pending_handbook'
    )),
    effective_on TEXT,
    expires_on TEXT,
    created_by_hr_user TEXT NOT NULL,
    reviewed_by_hr_user TEXT,
    created_at_utc TEXT NOT NULL,
    reviewed_at_utc TEXT,
    resource_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_case_resolutions_reuse
    ON case_resolutions(reuse_status, resolution_type, resolution_scope, created_at_utc DESC);
