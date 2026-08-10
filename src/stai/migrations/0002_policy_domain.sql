CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seed_manifests (
    dataset_name TEXT PRIMARY KEY,
    dataset_version TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    applied_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hires (
    hire_id TEXT PRIMARY KEY CHECK(hire_id = 'emp-alyssa'),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hire_profiles (
    hire_id TEXT PRIMARY KEY REFERENCES hires(hire_id) ON DELETE CASCADE,
    role_key TEXT NOT NULL CHECK(role_key IN ('branch_banking_associate','client_service_associate','digital_banking_support_associate')),
    department_key TEXT NOT NULL CHECK(department_key IN ('branch_banking','branch_operations','digital_channels')),
    employment_classification TEXT NOT NULL CHECK(employment_classification IN ('probationary','regular','fixed_term')),
    work_site TEXT NOT NULL CHECK(work_site IN ('branch','head_office','remote')),
    profile_revision INTEGER NOT NULL CHECK(profile_revision >= 1),
    updated_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hire_attribute_revisions (
    revision_id TEXT PRIMARY KEY, hire_id TEXT NOT NULL REFERENCES hires(hire_id) ON DELETE CASCADE,
    attribute_name TEXT NOT NULL, previous_value TEXT NOT NULL, new_value TEXT NOT NULL,
    resulting_profile_revision INTEGER NOT NULL, confirming_hr_user TEXT NOT NULL, effective_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attribute_change_requests (
    request_id TEXT PRIMARY KEY, hire_id TEXT NOT NULL REFERENCES hires(hire_id) ON DELETE CASCADE,
    attribute_name TEXT NOT NULL, current_value TEXT NOT NULL, proposed_value TEXT NOT NULL,
    profile_revision INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
    confirming_hr_user TEXT, created_at_utc TEXT NOT NULL, resolved_at_utc TEXT, resource_version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS policy_conversations (
    conversation_id TEXT PRIMARY KEY, hire_id TEXT NOT NULL REFERENCES hires(hire_id) ON DELETE CASCADE,
    simulated_date TEXT NOT NULL, created_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL, resource_version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS policy_messages (
    message_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES policy_conversations(conversation_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL, role TEXT NOT NULL CHECK(role IN ('hire','aisha')), text TEXT NOT NULL,
    response_type TEXT, created_at_utc TEXT NOT NULL, UNIQUE(conversation_id, ordinal)
);
CREATE TABLE IF NOT EXISTS policy_response_policies (
    message_id TEXT NOT NULL REFERENCES policy_messages(message_id) ON DELETE CASCADE,
    policy_id TEXT NOT NULL, handbook_version TEXT NOT NULL, policy_revision TEXT NOT NULL,
    profile_revision INTEGER NOT NULL, applicability TEXT NOT NULL CHECK(applicability IN ('applies','does_not_apply','needs_clarification')),
    evidence_state TEXT NOT NULL, PRIMARY KEY(message_id, policy_id)
);
CREATE TABLE IF NOT EXISTS policy_response_citations (
    message_id TEXT NOT NULL REFERENCES policy_messages(message_id) ON DELETE CASCADE,
    claim_ordinal INTEGER NOT NULL, policy_id TEXT NOT NULL, handbook_version TEXT NOT NULL,
    page_start INTEGER NOT NULL CHECK(page_start > 0), page_end INTEGER, PRIMARY KEY(message_id, claim_ordinal, policy_id, page_start)
);
CREATE TABLE IF NOT EXISTS escalation_offers (
    offer_id TEXT PRIMARY KEY, hire_id TEXT NOT NULL REFERENCES hires(hire_id) ON DELETE CASCADE,
    conversation_id TEXT REFERENCES policy_conversations(conversation_id) ON DELETE CASCADE, message_id TEXT,
    topic TEXT NOT NULL, route_owner TEXT NOT NULL, route_channel TEXT NOT NULL, proposed_summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status='pending'), expires_at_utc TEXT NOT NULL,
    created_at_utc TEXT NOT NULL, resource_version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS escalation_offer_policies (offer_id TEXT REFERENCES escalation_offers(offer_id) ON DELETE CASCADE, policy_id TEXT NOT NULL, PRIMARY KEY(offer_id, policy_id));
CREATE TABLE IF NOT EXISTS escalation_cases (
    case_id TEXT PRIMARY KEY, hire_id TEXT NOT NULL REFERENCES hires(hire_id) ON DELETE CASCADE,
    topic TEXT NOT NULL, approved_summary TEXT NOT NULL, route_owner TEXT NOT NULL, route_channel TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('open','closed')), created_at_utc TEXT NOT NULL, closed_at_utc TEXT,
    closing_hr_user TEXT, resource_version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS escalation_case_policies (case_id TEXT REFERENCES escalation_cases(case_id) ON DELETE CASCADE, policy_id TEXT NOT NULL, PRIMARY KEY(case_id, policy_id));
CREATE TABLE IF NOT EXISTS validation_results (
    validation_id TEXT PRIMARY KEY, hire_id TEXT NOT NULL REFERENCES hires(hire_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('complete','incomplete','needs_human_review')),
    policy_id TEXT NOT NULL CHECK(policy_id='HRP-004'), handbook_version TEXT NOT NULL, profile_revision INTEGER NOT NULL,
    accepted_attempt_count INTEGER NOT NULL CHECK(accepted_attempt_count IN (1,2)), simulated_evaluation_date TEXT NOT NULL,
    created_at_utc TEXT NOT NULL, document_fingerprint TEXT, share_state TEXT NOT NULL DEFAULT 'private' CHECK(share_state IN ('private','shared')),
    shared_at_utc TEXT, resource_version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS validation_result_codes (
    validation_id TEXT REFERENCES validation_results(validation_id) ON DELETE CASCADE,
    code_family TEXT NOT NULL CHECK(code_family IN ('missing','inconsistency','warning','human_review')),
    code TEXT NOT NULL, ordinal INTEGER NOT NULL, PRIMARY KEY(validation_id, code_family, ordinal)
);
CREATE TABLE IF NOT EXISTS validation_result_citations (
    validation_id TEXT REFERENCES validation_results(validation_id) ON DELETE CASCADE,
    policy_id TEXT NOT NULL, handbook_version TEXT NOT NULL, page_start INTEGER NOT NULL, page_end INTEGER,
    PRIMARY KEY(validation_id, policy_id, page_start)
);
CREATE TABLE IF NOT EXISTS certificate_retry_sessions (
    token_digest TEXT PRIMARY KEY, hire_id TEXT NOT NULL REFERENCES hires(hire_id) ON DELETE CASCADE,
    policy_id TEXT NOT NULL, handbook_version TEXT NOT NULL, profile_revision INTEGER NOT NULL,
    first_attempt_fingerprint TEXT NOT NULL, accepted_attempt_count INTEGER NOT NULL, created_at_utc TEXT NOT NULL, expires_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS holiday_cache (
    provider TEXT NOT NULL CHECK(provider='nager'), country TEXT NOT NULL CHECK(country='PH'), year INTEGER NOT NULL,
    payload_json TEXT NOT NULL, retrieved_at_utc TEXT NOT NULL, expires_at_utc TEXT NOT NULL,
    PRIMARY KEY(provider, country, year)
);
CREATE TABLE IF NOT EXISTS idempotency_records (
    operation_scope TEXT NOT NULL, key_digest TEXT NOT NULL, request_digest TEXT NOT NULL,
    target_resource_type TEXT, target_resource_id TEXT, target_resource_version INTEGER,
    http_status INTEGER NOT NULL, outcome_code TEXT NOT NULL, created_at_utc TEXT NOT NULL, expires_at_utc TEXT NOT NULL,
    PRIMARY KEY(operation_scope, key_digest)
);
CREATE TABLE IF NOT EXISTS retrieval_builds (
    build_id TEXT PRIMARY KEY, handbook_version TEXT NOT NULL, manifest_identity TEXT NOT NULL,
    collection_name TEXT NOT NULL UNIQUE, build_kind TEXT NOT NULL CHECK(build_kind IN ('production','evaluation')),
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('staging','verified','active','previous','failed')),
    created_at_utc TEXT NOT NULL, verified_at_utc TEXT, activated_at_utc TEXT
);
CREATE TABLE IF NOT EXISTS active_retrieval_build (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1), active_build_id TEXT REFERENCES retrieval_builds(build_id),
    previous_build_id TEXT REFERENCES retrieval_builds(build_id), generation INTEGER NOT NULL DEFAULT 0, switched_at_utc TEXT
);
CREATE INDEX IF NOT EXISTS idx_policy_messages_conversation ON policy_messages(conversation_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_validation_results_hire_created ON validation_results(hire_id, created_at_utc DESC, validation_id DESC);
CREATE INDEX IF NOT EXISTS idx_escalation_cases_status_created ON escalation_cases(status, created_at_utc DESC, case_id DESC);
CREATE INDEX IF NOT EXISTS idx_attribute_requests_status_created ON attribute_change_requests(status, created_at_utc DESC, request_id DESC);
