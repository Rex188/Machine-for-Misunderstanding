-- ==============================================================================
-- schema.sql — Canonical 10-Table SQLite Relational Schema
-- Project 2: A Machine for Misunderstanding (Blind Test Experiment)
-- Authoritative Source of Truth
-- ==============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

-- 1. Sessions: Global experiment container and versioning
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    status TEXT NOT NULL,
    current_round_index INTEGER NOT NULL DEFAULT 0,
    max_rounds INTEGER NOT NULL DEFAULT 3,
    version INTEGER NOT NULL DEFAULT 0,
    settings_json TEXT NOT NULL,
    continuation_votes_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    settled_at TEXT
);

-- 2. Participants: Dual-subject registry and token authentication
CREATE TABLE IF NOT EXISTS participants (
    participant_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    label TEXT NOT NULL CHECK (label IN ('A', 'B')),
    client_token_hash TEXT NOT NULL,
    connected INTEGER NOT NULL DEFAULT 1,
    ready INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(session_id, label)
);

-- 3. Rounds: Exchange container linking sender, receiver and marker
CREATE TABLE IF NOT EXISTS rounds (
    round_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    round_index INTEGER NOT NULL,
    sender_id TEXT NOT NULL REFERENCES participants(participant_id),
    receiver_id TEXT NOT NULL REFERENCES participants(participant_id),
    status TEXT NOT NULL,
    input_event_id TEXT UNIQUE,
    model_run_id TEXT UNIQUE,
    marker_id TEXT UNIQUE,
    receiver_response_id TEXT UNIQUE,
    metrics_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(session_id, round_index)
);

-- 4. Input Events: Immutable audit of sender somatic texts and self-assessments
CREATE TABLE IF NOT EXISTS input_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    round_id TEXT NOT NULL REFERENCES rounds(round_id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL REFERENCES participants(participant_id),
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    input_vadc_json TEXT NOT NULL,
    client_submission_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    monotonic_ms REAL,
    UNIQUE(session_id, client_submission_id)
);

-- 5. Model Runs: Inference output, latency and explicit fallback tracking
CREATE TABLE IF NOT EXISTS model_runs (
    model_run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    round_id TEXT NOT NULL REFERENCES rounds(round_id) ON DELETE CASCADE,
    backend TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    input_event_id TEXT NOT NULL REFERENCES input_events(event_id) ON DELETE CASCADE,
    input_hash TEXT NOT NULL,
    output_json TEXT,
    raw_output TEXT,
    status TEXT NOT NULL,
    fallback_used INTEGER NOT NULL DEFAULT 0,
    fallback_reason TEXT,
    latency_ms INTEGER,
    created_at TEXT NOT NULL
);

-- 6. Markers: Authoritative temporal acoustic anchor points
CREATE TABLE IF NOT EXISTS markers (
    marker_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    round_id TEXT NOT NULL REFERENCES rounds(round_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    sender_id TEXT NOT NULL REFERENCES participants(participant_id),
    receiver_id TEXT NOT NULL REFERENCES participants(participant_id),
    model_run_id TEXT NOT NULL REFERENCES model_runs(model_run_id) ON DELETE CASCADE,
    input_event_id TEXT NOT NULL REFERENCES input_events(event_id) ON DELETE CASCADE,
    acoustic_state_json TEXT NOT NULL,
    osc_dispatch_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    monotonic_ms REAL,
    UNIQUE(session_id, sequence),
    UNIQUE(session_id, round_id)
);

-- 7. Receiver Responses: Receiver evaluation, perceived VADC, and somatic shift
CREATE TABLE IF NOT EXISTS receiver_responses (
    receiver_response_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    round_id TEXT NOT NULL REFERENCES rounds(round_id) ON DELETE CASCADE,
    marker_id TEXT NOT NULL REFERENCES markers(marker_id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL REFERENCES participants(participant_id),
    receiver_vadc_json TEXT NOT NULL,
    somatic_shift TEXT NOT NULL,
    listening_confirmed INTEGER NOT NULL DEFAULT 1,
    submitted_at TEXT NOT NULL,
    client_version INTEGER
);

-- 8. Metrics: Pure geometric distances and decoupled confidence metrics
CREATE TABLE IF NOT EXISTS metrics (
    metrics_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    round_id TEXT NOT NULL REFERENCES rounds(round_id) ON DELETE CASCADE,
    marker_id TEXT NOT NULL REFERENCES markers(marker_id) ON DELETE CASCADE,
    formula_version TEXT NOT NULL DEFAULT 'metrics-v1',
    raw_distance_json TEXT NOT NULL,
    confidence_adjusted_distance_json TEXT NOT NULL,
    confidence_json TEXT NOT NULL,
    inter_round_drift REAL,
    created_at TEXT NOT NULL
);

-- 9. State Events: Append-only state machine transition audit trail
CREATE TABLE IF NOT EXISTS state_events (
    state_event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    round_id TEXT REFERENCES rounds(round_id) ON DELETE CASCADE,
    actor_id TEXT REFERENCES participants(participant_id),
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    monotonic_ms REAL
);

-- 10. Artifacts: External audiovisual recording files linked to markers
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT,
    started_at TEXT,
    ended_at TEXT,
    status TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

-- Performance indices for relational traversal and state projections
CREATE INDEX IF NOT EXISTS idx_participants_session ON participants(session_id);
CREATE INDEX IF NOT EXISTS idx_rounds_session ON rounds(session_id);
CREATE INDEX IF NOT EXISTS idx_input_events_round ON input_events(round_id);
CREATE INDEX IF NOT EXISTS idx_markers_session ON markers(session_id);
CREATE INDEX IF NOT EXISTS idx_receiver_responses_round ON receiver_responses(round_id);
CREATE INDEX IF NOT EXISTS idx_state_events_session ON state_events(session_id);
