"""
server.py — Multi-threaded HTTP Session Gateway & API Integration
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Architecture:
- Built with standard library http.server.ThreadingHTTPServer.
- Zero business logic inside handler: parses HTTP, verifies X-Session-Token hash,
  validates payload, delegates exclusively to BlindTestService, and returns
  privacy-sanitized projections.
- Thread-local SQLite connection isolation via db.py (no shared cursors/connections).
- Standardized error format without Python traceback leakage:
  {
    "error": {
      "code": "INVALID_STATE",
      "message": "...",
      "retryable": false
    },
    "version": <int or None>
  }
- Long polling for GET /api/blind/state?session_id=...&version=...
  If version matches current version, wait up to max_wait (default 20s, configurable)
  using threading.Condition triggered upon state updates.
"""

from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import logging
import os
import secrets
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import uuid

from db import Database, hash_token
from service import BlindTestService
from state_machine import (
    STATE_LOBBY,
    STATE_READY,
    STATE_INPUT_OPEN,
    STATE_MODEL_PROCESSING,
    STATE_SOUND_UPDATE,
    STATE_RECEIVER_RESPONSE,
    STATE_ROUND_COMPLETE,
    STATE_NEXT_ROUND_PENDING,
    STATE_SETTLEMENT,
    STATE_ERROR,
    STATE_ABORTED,
)

logger = logging.getLogger("blind_test.server")


class StateUpdateNotifier:
    """Thread-safe condition variable registry to unblock long-pollers on state change."""

    def __init__(self):
        self._lock = threading.Lock()
        self._conditions: Dict[str, threading.Condition] = {}

    def get_condition(self, session_id: str) -> threading.Condition:
        with self._lock:
            if session_id not in self._conditions:
                self._conditions[session_id] = threading.Condition()
            return self._conditions[session_id]

    def notify(self, session_id: str) -> None:
        with self._lock:
            cond = self._conditions.get(session_id)
        if cond:
            with cond:
                cond.notify_all()


class BlindTestHTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler for Blind Test API.
    Does NOT store session state in self. All state reads and writes flow through service.
    """

    # Attached at server initialization
    service: BlindTestService
    notifier: StateUpdateNotifier
    long_poll_timeout: float = 20.0

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stderr HTTP access logs in test/prod unless debug enabled."""
        pass

    # ── Response Helpers ──────────────────────────────────────────────────────

    def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(
        self,
        status_code: int,
        code: str,
        message: str,
        retryable: bool = False,
        version: Optional[int] = None,
    ) -> None:
        self._send_json(
            status_code,
            {
                "error": {
                    "code": code,
                    "message": message,
                    "retryable": retryable,
                },
                "version": version,
            },
        )

    # ── Request Body Parsing ──────────────────────────────────────────────────

    def _read_json_body(self) -> Optional[Dict[str, Any]]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_error(400, "BAD_REQUEST", "Missing or empty request body")
                return None
            body_bytes = self.rfile.read(content_length)
            return json.loads(body_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._send_error(400, "INVALID_JSON", "Malformed JSON payload")
            return None

    # ── Authentication Helper ─────────────────────────────────────────────────

    def _authenticate_participant(
        self, session_id: str, participant_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Authenticate participant using the X-Session-Token header against token hash in SQLite.
        Returns (is_valid, error_reason).
        """
        token = self.headers.get("X-Session-Token")
        if not token:
            return False, "Missing required X-Session-Token header"

        participant = self.service.db.get_participant(participant_id)
        if not participant:
            return False, f"Participant '{participant_id}' not found"

        if participant["session_id"] != session_id:
            return False, f"Participant '{participant_id}' does not belong to session '{session_id}'"

        expected_hash = hash_token(token)
        if participant.get("client_token_hash") != expected_hash:
            return False, "Invalid or unauthorized session token"

        return True, None

    def _verify_session_token(self, session_id: str) -> bool:
        """
        Verify that the X-Session-Token header matches any registered participant in the session.
        """
        token = self.headers.get("X-Session-Token")
        if not token:
            return False
        token_hash = hash_token(token)
        participants = self.service.db.get_participants(session_id)
        return any(p.get("client_token_hash") == token_hash for p in participants)

    # ── OPTIONS (CORS preflight) ──────────────────────────────────────────────

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ── GET Handlers ──────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        try:
            if path == "/api/blind/health":
                self._handle_health()
            elif path == "/api/blind/state":
                self._handle_get_state(query_params)
            elif path == "/api/blind/summary":
                self._handle_get_summary(query_params)
            elif path == "/api/blind/reveal":
                self._handle_get_reveal(query_params)
            else:
                self._send_error(404, "NOT_FOUND", f"Route GET {path} not found")
        except Exception as e:
            # Shield internal traceback from client
            logger.exception("Unexpected server error on GET %s: %s", path, str(e))
            self._send_error(500, "INTERNAL_ERROR", "An internal server error occurred")

    def _handle_health(self) -> None:
        self._send_json(200, {"status": "ok", "timestamp": time.time()})

    def _handle_get_state(self, query: Dict[str, list]) -> None:
        session_id_list = query.get("session_id")
        if not session_id_list or not session_id_list[0]:
            self._send_error(400, "MISSING_PARAMETER", "Query parameter 'session_id' is required")
            return

        session_id = session_id_list[0]
        session = self.service.db.get_session(session_id)
        if not session:
            self._send_error(404, "SESSION_NOT_FOUND", f"Session '{session_id}' does not exist")
            return

        participant_id_list = query.get("participant_id")
        actor_id: Optional[str] = None
        if participant_id_list and participant_id_list[0]:
            actor_id = participant_id_list[0]
            valid, err = self._authenticate_participant(session_id, actor_id)
            if not valid:
                self._send_error(401, "UNAUTHORIZED", err or "Unauthorized")
                return

        # ── Anonymous Access Restrictions ──
        # If no valid participant token is provided:
        if not actor_id:
            participants = self.service.db.get_participants(session_id)
            # In LOBBY, return minimal count without leaking internal participant IDs/tokens
            if session["status"] == STATE_LOBBY:
                self._send_json(
                    200,
                    {
                        "status": "LOBBY",
                        "participant_count": len(participants),
                    },
                )
                return
            else:
                # Once past LOBBY (READY, INPUT_OPEN, etc.), anonymous state probing is strictly forbidden
                self._send_error(
                    401,
                    "UNAUTHORIZED",
                    "Session is in progress or completed; state query requires participant authentication",
                    version=session.get("version"),
                )
                return

        # Long-polling check
        version_list = query.get("version")
        client_version: Optional[int] = None
        if version_list and version_list[0].isdigit():
            client_version = int(version_list[0])

        current_version = int(session.get("version", 0))

        if client_version is not None and client_version == current_version:
            cond = self.notifier.get_condition(session_id)
            deadline = time.time() + self.long_poll_timeout
            with cond:
                while time.time() < deadline:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break
                    cond.wait(timeout=remaining)
                    session = self.service.db.get_session(session_id)
                    if session and int(session.get("version", 0)) > client_version:
                        break

            session = self.service.db.get_session(session_id)
            if not session:
                self._send_error(404, "SESSION_NOT_FOUND", f"Session '{session_id}' not found")
                return
            new_version = int(session.get("version", 0))
            if new_version == client_version:
                projection = self.service.get_projection(session_id, actor_id)
                projection["unchanged"] = True
                self._send_json(200, projection)
                return

        projection = self.service.get_projection(session_id, actor_id)
        projection["unchanged"] = False
        self._send_json(200, projection)

    def _handle_get_summary(self, query: Dict[str, list]) -> None:
        session_id_list = query.get("session_id")
        if not session_id_list or not session_id_list[0]:
            self._send_error(400, "MISSING_PARAMETER", "Query parameter 'session_id' is required")
            return

        session_id = session_id_list[0]
        session = self.service.db.get_session(session_id)
        if not session:
            self._send_error(404, "SESSION_NOT_FOUND", f"Session '{session_id}' does not exist")
            return

        # ── Contract: /api/blind/summary requires participant token even after settlement ──
        participant_id_list = query.get("participant_id")
        if participant_id_list and participant_id_list[0]:
            valid, err = self._authenticate_participant(session_id, participant_id_list[0])
            if not valid:
                self._send_error(401, "UNAUTHORIZED", err or "Unauthorized")
                return
        else:
            # Fallback: check if header X-Session-Token matches any participant in the session
            if not self._verify_session_token(session_id):
                self._send_error(
                    401,
                    "UNAUTHORIZED",
                    "Viewing session summary requires valid X-Session-Token or participant authentication",
                )
                return

        if session["status"] not in (STATE_SETTLEMENT, STATE_ABORTED):
            self._send_error(
                403,
                "NOT_SETTLED",
                f"Full session summary is only accessible after settlement (current state: {session['status']})",
                version=session.get("version"),
            )
            return

        summary = self.service.db.get_full_session(session_id)
        self._send_json(200, summary)

    def _handle_get_reveal(self, query: Dict[str, list]) -> None:
        """
        Public/exhibition reveal endpoint using unguessable reveal_token from session settings.
        GET /api/blind/reveal?session_id=...&reveal_token=...
        """
        session_id_list = query.get("session_id")
        if not session_id_list or not session_id_list[0]:
            self._send_error(400, "MISSING_PARAMETER", "Query parameter 'session_id' is required")
            return

        reveal_token_list = query.get("reveal_token")
        if not reveal_token_list or not reveal_token_list[0]:
            self._send_error(400, "MISSING_PARAMETER", "Query parameter 'reveal_token' is required")
            return

        session_id = session_id_list[0]
        reveal_token = reveal_token_list[0]
        session = self.service.db.get_session(session_id)
        if not session:
            self._send_error(404, "SESSION_NOT_FOUND", f"Session '{session_id}' does not exist")
            return

        if session["status"] not in (STATE_SETTLEMENT, STATE_ABORTED):
            self._send_error(
                403,
                "NOT_SETTLED",
                f"Session is not settled yet (current state: {session['status']})",
                version=session.get("version"),
            )
            return

        expected_token = session.get("settings", {}).get("reveal_token")
        if not expected_token or not secrets.compare_digest(reveal_token, expected_token):
            self._send_error(403, "FORBIDDEN", "Invalid or expired reveal token")
            return

        summary = self.service.db.get_full_session(session_id)
        self._send_json(200, summary)

    # ── POST Handlers ─────────────────────────────────────────────────────────

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        try:
            if path == "/api/blind/join":
                self._handle_post_join()
            elif path == "/api/blind/ready":
                self._handle_post_ready()
            elif path == "/api/blind/start":
                self._handle_post_start()
            elif path == "/api/blind/submit_input":
                self._handle_post_submit_input()
            elif path == "/api/blind/submit_receiver":
                self._handle_post_submit_receiver()
            elif path == "/api/blind/continue":
                self._handle_post_continue()
            elif path == "/api/blind/end":
                self._handle_post_end()
            else:
                self._send_error(404, "NOT_FOUND", f"Route POST {path} not found")
        except Exception as e:
            # Shield internal traceback from client
            logger.exception("Unexpected server error on POST %s: %s", path, str(e))
            self._send_error(500, "INTERNAL_ERROR", "An internal server error occurred")

    def _handle_post_join(self) -> None:
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get("session_id")
        payload = data.get("payload", {})
        label = payload.get("label") or data.get("label")
        client_token = payload.get("client_token") or data.get("client_token")

        if not session_id or not label or not client_token:
            self._send_error(
                400,
                "MISSING_PARAMETER",
                "Fields 'session_id', 'label' ('A'|'B'), and 'client_token' are required",
            )
            return

        res = self.service.join(session_id=session_id, label=label, client_token=client_token)
        if not res.get("accepted"):
            self._send_error(400, "JOIN_REJECTED", res.get("reason", "Join rejected"))
            return

        self.notifier.notify(session_id)
        self._send_json(200, res)

    def _handle_post_ready(self) -> None:
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get("session_id")
        participant_id = data.get("participant_id")
        if not session_id or not participant_id:
            self._send_error(400, "MISSING_PARAMETER", "Fields 'session_id' and 'participant_id' are required")
            return

        valid, err = self._authenticate_participant(session_id, participant_id)
        if not valid:
            self._send_error(401, "UNAUTHORIZED", err or "Unauthorized")
            return

        res = self.service.ready(session_id=session_id, actor_id=participant_id)
        if not res.get("accepted"):
            self._send_error(400, "READY_REJECTED", res.get("reason", "Ready rejected"))
            return

        self.notifier.notify(session_id)
        projection = self.service.get_projection(session_id, participant_id)
        self._send_json(200, projection)

    def _handle_post_start(self) -> None:
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get("session_id")
        participant_id = data.get("participant_id")
        if not session_id:
            self._send_error(400, "MISSING_PARAMETER", "Field 'session_id' is required")
            return

        if participant_id:
            valid, err = self._authenticate_participant(session_id, participant_id)
            if not valid:
                self._send_error(401, "UNAUTHORIZED", err or "Unauthorized")
                return

        res = self.service.start_session(session_id=session_id)
        if not res.get("accepted"):
            self._send_error(400, "START_REJECTED", res.get("reason", "Start session rejected"))
            return

        self.notifier.notify(session_id)
        projection = self.service.get_projection(session_id, participant_id)
        self._send_json(200, projection)

    def _handle_post_submit_input(self) -> None:
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get("session_id")
        participant_id = data.get("participant_id")
        client_version = data.get("client_version")
        idempotency_key = data.get("idempotency_key")
        payload = data.get("payload", {})

        text = payload.get("text")
        input_vadc = payload.get("input_vadc")
        client_submission_id = payload.get("client_submission_id") or f"sub_{uuid.uuid4().hex[:12]}"

        if not session_id or not participant_id or not text or not input_vadc:
            self._send_error(
                400,
                "MISSING_PARAMETER",
                "Fields 'session_id', 'participant_id', 'payload.text', and 'payload.input_vadc' are required",
            )
            return

        valid, err = self._authenticate_participant(session_id, participant_id)
        if not valid:
            self._send_error(401, "UNAUTHORIZED", err or "Unauthorized")
            return

        session = self.service.db.get_session(session_id)
        current_version = session.get("version") if session else None

        try:
            res = self.service.submit_input(
                session_id=session_id,
                actor_id=participant_id,
                text=text,
                input_vadc=input_vadc,
                client_submission_id=client_submission_id,
                client_version=client_version,
                idempotency_key=idempotency_key,
            )
        except Exception as e:
            # Handle possible concurrent race condition gracefully
            if "UNIQUE constraint failed" in str(e) or "constraint failed" in str(e):
                self._send_error(400, "CONCURRENT_CONFLICT", "Conflicting submission already registered", version=current_version)
                return
            raise

        if not res.get("accepted"):
            err_code = "SUBMISSION_REJECTED"
            reason = res.get("reason") or res.get("error", "Input submission rejected")
            if "Stale client version" in reason:
                err_code = "STALE_VERSION"
            elif "not the current sender" in reason:
                err_code = "ROLE_MISMATCH"
            self._send_error(400, err_code, reason, version=current_version)
            return

        self.notifier.notify(session_id)
        projection = self.service.get_projection(session_id, participant_id)
        self._send_json(200, projection)

    def _handle_post_submit_receiver(self) -> None:
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get("session_id")
        participant_id = data.get("participant_id")
        client_version = data.get("client_version")
        idempotency_key = data.get("idempotency_key")
        payload = data.get("payload", {})

        receiver_vadc = payload.get("receiver_vadc")
        somatic_shift = payload.get("somatic_shift", "")
        listening_confirmed = payload.get("listening_confirmed", True)

        if not session_id or not participant_id or not receiver_vadc:
            self._send_error(
                400,
                "MISSING_PARAMETER",
                "Fields 'session_id', 'participant_id', and 'payload.receiver_vadc' are required",
            )
            return

        valid, err = self._authenticate_participant(session_id, participant_id)
        if not valid:
            self._send_error(401, "UNAUTHORIZED", err or "Unauthorized")
            return

        session = self.service.db.get_session(session_id)
        current_version = session.get("version") if session else None

        res = self.service.submit_receiver_response(
            session_id=session_id,
            actor_id=participant_id,
            receiver_vadc=receiver_vadc,
            somatic_shift=somatic_shift,
            listening_confirmed=listening_confirmed,
            client_version=client_version,
            idempotency_key=idempotency_key,
        )

        if not res.get("accepted"):
            err_code = "SUBMISSION_REJECTED"
            reason = res.get("reason") or res.get("error", "Receiver submission rejected")
            if "Stale client version" in reason:
                err_code = "STALE_VERSION"
            elif "not the current receiver" in reason:
                err_code = "ROLE_MISMATCH"
            self._send_error(400, err_code, reason, version=current_version)
            return

        self.notifier.notify(session_id)
        projection = self.service.get_projection(session_id, participant_id)
        self._send_json(200, projection)

    def _handle_post_continue(self) -> None:
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get("session_id")
        participant_id = data.get("participant_id")
        if not session_id or not participant_id:
            self._send_error(400, "MISSING_PARAMETER", "Fields 'session_id' and 'participant_id' are required")
            return

        valid, err = self._authenticate_participant(session_id, participant_id)
        if not valid:
            self._send_error(401, "UNAUTHORIZED", err or "Unauthorized")
            return

        res = self.service.choose_continue(session_id=session_id, actor_id=participant_id)
        if not res.get("accepted"):
            self._send_error(400, "CONTINUE_REJECTED", res.get("reason", "Continuation rejected"))
            return

        self.notifier.notify(session_id)
        projection = self.service.get_projection(session_id, participant_id)
        self._send_json(200, projection)

    def _handle_post_end(self) -> None:
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get("session_id")
        participant_id = data.get("participant_id")
        if not session_id or not participant_id:
            self._send_error(400, "MISSING_PARAMETER", "Fields 'session_id' and 'participant_id' are required")
            return

        valid, err = self._authenticate_participant(session_id, participant_id)
        if not valid:
            self._send_error(401, "UNAUTHORIZED", err or "Unauthorized")
            return

        res = self.service.end_session(session_id=session_id, actor_id=participant_id)
        if not res.get("accepted"):
            self._send_error(400, "END_REJECTED", res.get("reason", "End session rejected"))
            return

        self.notifier.notify(session_id)
        # When session ends, projection returns settled / revealed session
        projection = self.service.get_projection(session_id, participant_id)
        self._send_json(200, projection)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    service: Optional[BlindTestService] = None,
    long_poll_timeout: float = 20.0,
) -> ThreadingHTTPServer:
    """Factory creating configured ThreadingHTTPServer instance."""
    if service is None:
        raise ValueError("BlindTestService instance must be provided to create_server")

    notifier = StateUpdateNotifier()

    # Subclass handler to bind dependencies cleanly
    class ConfiguredHandler(BlindTestHTTPHandler):
        pass

    ConfiguredHandler.service = service
    ConfiguredHandler.notifier = notifier
    ConfiguredHandler.long_poll_timeout = long_poll_timeout

    server = ThreadingHTTPServer((host, port), ConfiguredHandler)
    return server
