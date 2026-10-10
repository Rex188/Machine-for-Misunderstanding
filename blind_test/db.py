"""
db.py — Authoritative SQLite Persistence & Transaction Layer
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Architecture:
- 10-table canonical relational schema matching BLIND_TEST_DATA_SCHEMA.md
- Thread-local SQLite connection pool (each thread owns its own connection)
- Strict PRAGMAs: foreign_keys = ON, journal_mode = WAL, busy_timeout = 5000
- Atomic transactions for sender input + marker creation, receiver response + metrics
"""

from datetime import datetime, timezone
import hashlib
import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "blind_test.db")


def utc_now_iso() -> str:
    """Return ISO-8601 timestamp with microsecond resolution and +08:00 or Z timezone."""
    return datetime.now().astimezone().isoformat()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Database:
    """Thread-safe SQLite Database Manager utilizing thread-local connections."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Get or initialize thread-local connection with strict PRAGMAs."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def close_current_thread_connection(self):
        """Close connection for the current thread if open."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

    def init_db(self, schema_file: str = SCHEMA_PATH):
        """Initialize all 10 tables and indices from schema.sql."""
        with open(schema_file, "r", encoding="utf-8") as f:
            sql = f.read()
        conn = self.get_connection()
        with conn:
            conn.executescript(sql)

    # ── Session Management ───────────────────────────────────────────────────

    def create_session(
        self,
        session_id: Optional[str] = None,
        max_rounds: int = 3,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new experiment session in LOBBY state."""
        conn = self.get_connection()
        if session_id is None:
            session_id = f"s_{int(time.time() * 1000):010d}"

        default_settings = {
            "confidence_alpha": 0.3,
            "require_both_to_continue": True,
            "audio_mode": "continuous_vcv",
            "recording_required": False,
        }
        if settings:
            default_settings.update(settings)

        now = utc_now_iso()
        with conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, schema_version, status, current_round_index,
                    max_rounds, version, settings_json, continuation_votes_json, created_at, updated_at
                ) VALUES (?, '1.0', 'LOBBY', 0, ?, 0, ?, '{}', ?, ?)
                """,
                (session_id, max_rounds, json.dumps(default_settings), now, now),
            )
            # Record initial state event
            conn.execute(
                """
                INSERT INTO state_events (
                    state_event_id, session_id, round_id, actor_id,
                    from_state, to_state, event_type, payload_json, created_at, monotonic_ms
                ) VALUES (?, ?, NULL, NULL, 'INIT', 'LOBBY', 'SESSION_CREATED', ?, ?, ?)
                """,
                (
                    f"se_{session_id}_0",
                    session_id,
                    json.dumps({"settings": default_settings}),
                    now,
                    time.monotonic() * 1000,
                ),
            )
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["settings"] = json.loads(d.pop("settings_json"))
        d["continuation_votes"] = json.loads(d.pop("continuation_votes_json", "{}"))
        return d

    def update_session_status(
        self, session_id: str, new_status: str, actor_id: Optional[str] = None, event_type: str = "STATUS_UPDATE"
    ):
        conn = self.get_connection()
        now = utc_now_iso()
        mono = time.monotonic() * 1000
        with conn:
            cur = conn.execute("SELECT status, version FROM sessions WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Session {session_id} not found")
            old_status, version = row["status"], row["version"]

            conn.execute(
                """
                UPDATE sessions
                SET status = ?, version = version + 1, updated_at = ?
                WHERE session_id = ?
                """,
                (new_status, now, session_id),
            )
            # State event
            conn.execute(
                """
                INSERT INTO state_events (
                    state_event_id, session_id, round_id, actor_id,
                    from_state, to_state, event_type, payload_json, created_at, monotonic_ms
                ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"se_{session_id}_{version + 1}",
                    session_id,
                    actor_id,
                    old_status,
                    new_status,
                    event_type,
                    json.dumps({}),
                    now,
                    mono,
                ),
            )

    def set_continuation_vote(self, session_id: str, participant_id: str, vote: str) -> Dict[str, str]:
        """Record a participant's continuation vote ('continue' or 'end')."""
        conn = self.get_connection()
        now = utc_now_iso()
        with conn:
            cur = conn.execute("SELECT continuation_votes_json FROM sessions WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Session {session_id} not found")
            votes = json.loads(row["continuation_votes_json"] or "{}")
            votes[participant_id] = vote
            conn.execute(
                """
                UPDATE sessions
                SET continuation_votes_json = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (json.dumps(votes), now, session_id),
            )
        return votes

    def reset_continuation_votes(self, session_id: str):
        """Clear continuation votes when a new round opens."""
        conn = self.get_connection()
        now = utc_now_iso()
        with conn:
            conn.execute(
                """
                UPDATE sessions
                SET continuation_votes_json = '{}', updated_at = ?
                WHERE session_id = ?
                """,
                (now, session_id),
            )

    # ── Participants ─────────────────────────────────────────────────────────

    def add_participant(
        self, session_id: str, label: str, client_token: str, participant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a participant with token hash."""
        if label not in ("A", "B"):
            raise ValueError(f"Invalid participant label '{label}'. Must be 'A' or 'B'.")
        conn = self.get_connection()
        if participant_id is None:
            participant_id = f"p_{session_id}_{label}"
        token_hash = hash_token(client_token)
        now = utc_now_iso()

        with conn:
            conn.execute(
                """
                INSERT INTO participants (
                    participant_id, session_id, label, client_token_hash,
                    connected, ready, joined_at, last_seen_at
                ) VALUES (?, ?, ?, ?, 1, 0, ?, ?)
                """,
                (participant_id, session_id, label, token_hash, now, now),
            )
            conn.execute(
                """
                UPDATE sessions
                SET version = version + 1, updated_at = ?
                WHERE session_id = ?
                """,
                (now, session_id),
            )
        return self.get_participant(participant_id)

    def get_participant(self, participant_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM participants WHERE participant_id = ?", (participant_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_participants(self, session_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute(
            "SELECT * FROM participants WHERE session_id = ? ORDER BY label ASC", (session_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    # ── Rounds ───────────────────────────────────────────────────────────────

    def create_round(
        self, session_id: str, round_index: int, sender_id: str, receiver_id: str, round_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new round container."""
        conn = self.get_connection()
        if round_id is None:
            round_id = f"r_{session_id}_{round_index + 1}"
        now = utc_now_iso()

        with conn:
            conn.execute(
                """
                INSERT INTO rounds (
                    round_id, session_id, round_index, sender_id, receiver_id,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'OPEN', ?)
                """,
                (round_id, session_id, round_index, sender_id, receiver_id, now),
            )
            # Update session current_round_index
            conn.execute(
                """
                UPDATE sessions
                SET current_round_index = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (round_index, now, session_id),
            )
        return self.get_round(round_id)

    def get_round(self, round_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM rounds WHERE round_id = ?", (round_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_rounds(self, session_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute(
            "SELECT * FROM rounds WHERE session_id = ? ORDER BY round_index ASC", (session_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    # ── Atomic Transaction 1: Sender Input + Model Run + Marker ──────────────

    def commit_sender_input_and_marker(
        self,
        session_id: str,
        round_id: str,
        actor_id: str,
        text: str,
        input_vadc: Dict[str, float],
        client_submission_id: str,
        model_backend: str,
        model_name: str,
        prompt_version: str,
        model_output: Dict[str, Any],
        raw_output: str,
        model_status: str,
        fallback_used: bool,
        fallback_reason: Optional[str],
        latency_ms: int,
        sequence: int,
        acoustic_state: Dict[str, Any],
        osc_dispatch: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Execute Section 16 Transaction Boundary 1:
        validate request -> create input event -> create model run ->
        validate acoustic output -> send OSC -> create marker ->
        update round state -> append state event -> increment session version.
        """
        conn = self.get_connection()
        now = utc_now_iso()
        mono = time.monotonic() * 1000
        event_id = f"e_{session_id}_{round_id}_in"
        model_run_id = f"mr_{session_id}_{round_id}"
        marker_id = f"m_{session_id}_{round_id}"

        # Fetch receiver_id for marker
        round_info = self.get_round(round_id)
        if not round_info:
            raise ValueError(f"Round {round_id} does not exist.")
        receiver_id = round_info["receiver_id"]
        t_hash = hash_text(text)

        with conn:
            # 1. Insert input_events
            conn.execute(
                """
                INSERT INTO input_events (
                    event_id, session_id, round_id, actor_id,
                    text, text_hash, input_vadc_json, client_submission_id,
                    created_at, monotonic_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    session_id,
                    round_id,
                    actor_id,
                    text,
                    t_hash,
                    json.dumps(input_vadc),
                    client_submission_id,
                    now,
                    mono,
                ),
            )

            # 2. Insert model_runs
            conn.execute(
                """
                INSERT INTO model_runs (
                    model_run_id, session_id, round_id, backend, model_name,
                    prompt_version, input_event_id, input_hash, output_json,
                    raw_output, status, fallback_used, fallback_reason,
                    latency_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_run_id,
                    session_id,
                    round_id,
                    model_backend,
                    model_name,
                    prompt_version,
                    event_id,
                    t_hash,
                    json.dumps(model_output),
                    raw_output,
                    model_status,
                    1 if fallback_used else 0,
                    fallback_reason,
                    latency_ms,
                    now,
                ),
            )

            # 3. Insert markers
            conn.execute(
                """
                INSERT INTO markers (
                    marker_id, session_id, round_id, sequence, event_id,
                    sender_id, receiver_id, model_run_id, input_event_id,
                    acoustic_state_json, osc_dispatch_json, status,
                    created_at, monotonic_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMMITTED', ?, ?)
                """,
                (
                    marker_id,
                    session_id,
                    round_id,
                    sequence,
                    event_id,
                    actor_id,
                    receiver_id,
                    model_run_id,
                    event_id,
                    json.dumps(acoustic_state),
                    json.dumps(osc_dispatch),
                    now,
                    mono,
                ),
            )

            # 4. Update round
            conn.execute(
                """
                UPDATE rounds
                SET input_event_id = ?, model_run_id = ?, marker_id = ?,
                    status = 'RECEIVER_RESPONSE'
                WHERE round_id = ?
                """,
                (event_id, model_run_id, marker_id, round_id),
            )

            # 5. Append state event
            conn.execute(
                """
                INSERT INTO state_events (
                    state_event_id, session_id, round_id, actor_id,
                    from_state, to_state, event_type, payload_json,
                    created_at, monotonic_ms
                ) VALUES (?, ?, ?, ?, 'INPUT_OPEN', 'RECEIVER_RESPONSE', 'MARKER_COMMITTED', ?, ?, ?)
                """,
                (
                    f"se_{session_id}_mk_{sequence}",
                    session_id,
                    round_id,
                    actor_id,
                    json.dumps({"marker_id": marker_id, "sequence": sequence}),
                    now,
                    mono,
                ),
            )

            # 6. Update session
            conn.execute(
                """
                UPDATE sessions
                SET status = 'RECEIVER_RESPONSE', version = version + 1, updated_at = ?
                WHERE session_id = ?
                """,
                (now, session_id),
            )

        return (
            self.get_input_event(event_id),
            self.get_model_run(model_run_id),
            self.get_marker(marker_id),
        )

    # ── Atomic Transaction 2: Receiver Response + Metrics ─────────────────────

    def commit_receiver_response_and_metrics(
        self,
        session_id: str,
        round_id: str,
        marker_id: str,
        actor_id: str,
        receiver_vadc: Dict[str, float],
        somatic_shift: str,
        raw_distance: Dict[str, float],
        confidence_adjusted_distance: Dict[str, float],
        confidence: Dict[str, float],
        inter_round_drift: Optional[float] = None,
        listening_confirmed: bool = True,
        formula_version: str = "metrics-v1-euclidean-drift",
        client_version: int = 1,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Execute Section 16 Transaction Boundary 2:
        validate response -> create receiver response -> calculate metrics ->
        update round state to COMPLETE -> append state event -> increment session version.
        """
        conn = self.get_connection()
        now = utc_now_iso()
        mono = time.monotonic() * 1000
        receiver_response_id = f"rr_{session_id}_{round_id}"
        metrics_id = f"metrics_{session_id}_{round_id}"

        with conn:
            # 1. Insert receiver_responses
            conn.execute(
                """
                INSERT INTO receiver_responses (
                    receiver_response_id, session_id, round_id, marker_id,
                    actor_id, receiver_vadc_json, somatic_shift,
                    listening_confirmed, submitted_at, client_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receiver_response_id,
                    session_id,
                    round_id,
                    marker_id,
                    actor_id,
                    json.dumps(receiver_vadc),
                    somatic_shift,
                    1 if listening_confirmed else 0,
                    now,
                    client_version,
                ),
            )

            # 2. Insert metrics
            conn.execute(
                """
                INSERT INTO metrics (
                    metrics_id, session_id, round_id, marker_id, formula_version,
                    raw_distance_json, confidence_adjusted_distance_json,
                    confidence_json, inter_round_drift, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metrics_id,
                    session_id,
                    round_id,
                    marker_id,
                    formula_version,
                    json.dumps(raw_distance),
                    json.dumps(confidence_adjusted_distance),
                    json.dumps(confidence),
                    inter_round_drift,
                    now,
                ),
            )

            # 3. Update round to COMPLETE
            conn.execute(
                """
                UPDATE rounds
                SET receiver_response_id = ?, metrics_id = ?,
                    status = 'COMPLETE', completed_at = ?
                WHERE round_id = ?
                """,
                (receiver_response_id, metrics_id, now, round_id),
            )

            # 4. Append state event
            conn.execute(
                """
                INSERT INTO state_events (
                    state_event_id, session_id, round_id, actor_id,
                    from_state, to_state, event_type, payload_json,
                    created_at, monotonic_ms
                ) VALUES (?, ?, ?, ?, 'RECEIVER_RESPONSE', 'ROUND_COMPLETE', 'RECEIVER_RESPONSE_SUBMITTED', ?, ?, ?)
                """,
                (
                    f"se_{session_id}_rr_{round_id}",
                    session_id,
                    round_id,
                    actor_id,
                    json.dumps({"metrics_id": metrics_id}),
                    now,
                    mono,
                ),
            )

            # 5. Update session
            conn.execute(
                """
                UPDATE sessions
                SET status = 'ROUND_COMPLETE', version = version + 1, updated_at = ?
                WHERE session_id = ?
                """,
                (now, session_id),
            )

        return (
            self.get_receiver_response(receiver_response_id),
            self.get_metrics(metrics_id),
        )

    # ── Single Entity Getters ────────────────────────────────────────────────

    def get_input_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM input_events WHERE event_id = ?", (event_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["input_vadc"] = json.loads(d.pop("input_vadc_json"))
        return d

    def get_model_run(self, model_run_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM model_runs WHERE model_run_id = ?", (model_run_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["output"] = json.loads(d.pop("output_json")) if d.get("output_json") else None
        d["fallback_used"] = bool(d["fallback_used"])
        return d

    def get_marker(self, marker_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM markers WHERE marker_id = ?", (marker_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["acoustic_state"] = json.loads(d.pop("acoustic_state_json"))
        d["osc_dispatch"] = json.loads(d.pop("osc_dispatch_json"))
        return d

    def get_receiver_response(self, receiver_response_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute(
            "SELECT * FROM receiver_responses WHERE receiver_response_id = ?", (receiver_response_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["receiver_vadc"] = json.loads(d.pop("receiver_vadc_json"))
        d["listening_confirmed"] = bool(d["listening_confirmed"])
        return d

    def get_metrics(self, metrics_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM metrics WHERE metrics_id = ?", (metrics_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["raw_distance"] = json.loads(d.pop("raw_distance_json"))
        d["confidence_adjusted_distance"] = json.loads(d.pop("confidence_adjusted_distance_json"))
        d["confidence"] = json.loads(d.pop("confidence_json"))
        return d

    # ── Canonical Export / Full Session Representation ────────────────────────

    def get_full_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the canonical complete session data matching Section 15 of BLIND_TEST_DATA_SCHEMA.md.
        Aggregates data across all 10 tables.
        """
        session = self.get_session(session_id)
        if not session:
            return None

        conn = self.get_connection()

        # Participants
        participants = self.get_participants(session_id)

        # Rounds
        rounds = self.get_rounds(session_id)

        # Input Events
        cur = conn.execute(
            "SELECT * FROM input_events WHERE session_id = ? ORDER BY created_at ASC", (session_id,)
        )
        input_events = []
        for r in cur.fetchall():
            row = dict(r)
            row["input_vadc"] = json.loads(row.pop("input_vadc_json"))
            input_events.append(row)

        # Model Runs
        cur = conn.execute(
            "SELECT * FROM model_runs WHERE session_id = ? ORDER BY created_at ASC", (session_id,)
        )
        model_runs = []
        for r in cur.fetchall():
            row = dict(r)
            row["output"] = json.loads(row.pop("output_json")) if row.get("output_json") else None
            row["fallback_used"] = bool(row["fallback_used"])
            model_runs.append(row)

        # Markers
        cur = conn.execute(
            "SELECT * FROM markers WHERE session_id = ? ORDER BY sequence ASC", (session_id,)
        )
        markers = []
        for r in cur.fetchall():
            row = dict(r)
            row["acoustic_state"] = json.loads(row.pop("acoustic_state_json"))
            row["osc_dispatch"] = json.loads(row.pop("osc_dispatch_json"))
            markers.append(row)

        # Receiver Responses
        cur = conn.execute(
            "SELECT * FROM receiver_responses WHERE session_id = ? ORDER BY submitted_at ASC", (session_id,)
        )
        receiver_responses = []
        for r in cur.fetchall():
            row = dict(r)
            row["receiver_vadc"] = json.loads(row.pop("receiver_vadc_json"))
            row["listening_confirmed"] = bool(row["listening_confirmed"])
            receiver_responses.append(row)

        # Metrics
        cur = conn.execute(
            "SELECT * FROM metrics WHERE session_id = ? ORDER BY created_at ASC", (session_id,)
        )
        metrics = []
        for r in cur.fetchall():
            row = dict(r)
            row["raw_distance"] = json.loads(row.pop("raw_distance_json"))
            row["confidence_adjusted_distance"] = json.loads(row.pop("confidence_adjusted_distance_json"))
            row["confidence"] = json.loads(row.pop("confidence_json"))
            metrics.append(row)

        # State Events
        cur = conn.execute(
            "SELECT * FROM state_events WHERE session_id = ? ORDER BY created_at ASC", (session_id,)
        )
        state_events = []
        for r in cur.fetchall():
            row = dict(r)
            row["payload"] = json.loads(row.pop("payload_json"))
            state_events.append(row)

        # Artifacts
        cur = conn.execute(
            "SELECT * FROM artifacts WHERE session_id = ? ORDER BY started_at ASC", (session_id,)
        )
        artifacts = [dict(r) for r in cur.fetchall()]

        return {
            "schema_version": "1.0",
            "session": session,
            "participants": participants,
            "rounds": rounds,
            "input_events": input_events,
            "model_runs": model_runs,
            "markers": markers,
            "receiver_responses": receiver_responses,
            "metrics": metrics,
            "state_events": state_events,
            "artifacts": artifacts,
        }
