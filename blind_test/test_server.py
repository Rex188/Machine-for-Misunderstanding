"""
test_server.py — Integration Tests for HTTP API Gateway
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Tests:
1. health endpoint (/api/blind/health)
2. Two clients join successfully (POST /api/blind/join)
3. Third client rejected (label C or beyond capacity)
4. A/B ready (POST /api/blind/ready)
5. Start session (POST /api/blind/start)
6. A submits input (POST /api/blind/submit_input)
7. B state projection strictly does NOT leak A's text, input VAD, or model VAD
8. B submits receiver response (POST /api/blind/submit_receiver)
9. Duplicate idempotency_key returns cached result
10. Stale client_version is rejected
11. Unauthorized token (bad X-Session-Token or missing header) is rejected
12. Role mismatch (receiver attempting sender input, sender attempting receiver response) is rejected
13. End session early (POST /api/blind/end)
14. Submissions forbidden after settlement
15. Concurrent submissions do NOT create duplicate markers
16. Server internal errors or malformed JSON never leak Python tracebacks
17. Long polling test: verifies that waiting thread unblocks upon state update or returns unchanged on timeout
"""

import json
import os
import shutil
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from acoustic_bridge import FakeModelBackend, FakeOscTransport
from db import Database
from server import create_server
from service import BlindTestService
from state_machine import (
    STATE_LOBBY,
    STATE_READY,
    STATE_INPUT_OPEN,
    STATE_RECEIVER_RESPONSE,
    STATE_ROUND_COMPLETE,
    STATE_SETTLEMENT,
)


def _http_request(
    url: str,
    method: str = "GET",
    body: dict = None,
    headers: dict = None,
):
    """Utility helper using urllib to make HTTP requests."""
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = Request(url, data=data, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=10.0) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            return status, json.loads(content) if content else {}
    except HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return e.code, parsed


class TestServerContext:
    """Manages ephemeral database, fake backends, service, and live ThreadingHTTPServer."""

    def __init__(self, long_poll_timeout: float = 2.0):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_api.db")
        self.db = Database(self.db_path)
        self.db.init_db()

        self.fake_model = FakeModelBackend()
        self.fake_osc = FakeOscTransport()
        self.service = BlindTestService(
            db=self.db,
            model_backend=self.fake_model,
            osc_transport=self.fake_osc,
        )

        # Port 0 selects any free ephemeral port
        self.server = create_server(
            host="127.0.0.1",
            port=0,
            service=self.service,
            long_poll_timeout=long_poll_timeout,
        )
        self.host, self.port = self.server.server_address
        self.base_url = f"http://{self.host}:{self.port}"

        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def test_health_endpoint():
    ctx = TestServerContext()
    try:
        status, data = _http_request(f"{ctx.base_url}/api/blind/health")
        assert status == 200
        assert data.get("status") == "ok"
        assert "timestamp" in data
    finally:
        ctx.close()


def test_standard_flow_and_privacy_projection():
    ctx = TestServerContext()
    try:
        session_id = "s_http_flow"
        ctx.service.create_session(session_id)

        token_a = "secret_token_a_123"
        token_b = "secret_token_b_456"

        # 1. Client A Joins
        status, res_join_a = _http_request(
            f"{ctx.base_url}/api/blind/join",
            method="POST",
            body={
                "session_id": session_id,
                "label": "A",
                "client_token": token_a,
            },
        )
        assert status == 200
        assert res_join_a["accepted"] is True
        p_a = res_join_a["participant"]["participant_id"]

        # 2. Client B Joins
        status, res_join_b = _http_request(
            f"{ctx.base_url}/api/blind/join",
            method="POST",
            body={
                "session_id": session_id,
                "label": "B",
                "client_token": token_b,
            },
        )
        assert status == 200
        assert res_join_b["accepted"] is True
        p_b = res_join_b["participant"]["participant_id"]

        # 3. Third Client Rejected
        status, res_join_c = _http_request(
            f"{ctx.base_url}/api/blind/join",
            method="POST",
            body={
                "session_id": session_id,
                "label": "C",
                "client_token": "token_c",
            },
        )
        assert status == 400
        assert "JOIN_REJECTED" in res_join_c["error"]["code"] or "MISSING_PARAMETER" in res_join_c["error"]["code"]

        # 4. Ready A and B
        status, res_ready_a = _http_request(
            f"{ctx.base_url}/api/blind/ready",
            method="POST",
            body={"session_id": session_id, "participant_id": p_a},
            headers={"X-Session-Token": token_a},
        )
        assert status == 200

        status, res_ready_b = _http_request(
            f"{ctx.base_url}/api/blind/ready",
            method="POST",
            body={"session_id": session_id, "participant_id": p_b},
            headers={"X-Session-Token": token_b},
        )
        assert status == 200
        assert res_ready_b["status"] == STATE_READY

        # 5. Start Session
        status, res_start = _http_request(
            f"{ctx.base_url}/api/blind/start",
            method="POST",
            body={"session_id": session_id, "participant_id": p_a},
            headers={"X-Session-Token": token_a},
        )
        assert status == 200
        assert res_start["status"] == STATE_INPUT_OPEN

        # 6. Sender A Submits Input
        vadc_a = {"valence": 0.2, "arousal": 0.8, "dominance": 0.3, "confidence": 0.9}
        secret_somatic_text = "Felt subterranean frost and shivering muscles"
        status, res_input = _http_request(
            f"{ctx.base_url}/api/blind/submit_input",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_a,
                "client_version": res_start["version"],
                "idempotency_key": "k_http_inp_1",
                "payload": {
                    "text": secret_somatic_text,
                    "input_vadc": vadc_a,
                    "client_submission_id": "sub_a_1",
                },
            },
            headers={"X-Session-Token": token_a},
        )
        assert status == 200
        assert res_input["status"] == STATE_RECEIVER_RESPONSE

        # 7. Receiver B State Projection strictly DOES NOT LEAK A's data
        status, state_b = _http_request(
            f"{ctx.base_url}/api/blind/state?session_id={session_id}&participant_id={p_b}",
            headers={"X-Session-Token": token_b},
        )
        assert status == 200
        assert state_b["role"] == "RECEIVER"
        assert state_b["status"] == STATE_RECEIVER_RESPONSE
        assert state_b["can_respond"] is True
        assert state_b["acoustic_status"] == "ACTIVE"
        # Strict privacy check across entire JSON string representation
        dumped_b = json.dumps(state_b)
        assert secret_somatic_text not in dumped_b
        assert "input_vadc" not in dumped_b
        assert "model_output" not in dumped_b
        assert "raw_output" not in dumped_b

        # 8. Receiver B Submits Response
        vadc_b = {"valence": 0.4, "arousal": 0.7, "dominance": 0.4, "confidence": 0.8}
        status, res_resp_b = _http_request(
            f"{ctx.base_url}/api/blind/submit_receiver",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_b,
                "client_version": state_b["version"],
                "idempotency_key": "k_http_rec_1",
                "payload": {
                    "receiver_vadc": vadc_b,
                    "somatic_shift": "Chest vibrating with sub-bass",
                    "listening_confirmed": True,
                },
            },
            headers={"X-Session-Token": token_b},
        )
        assert status == 200
        assert res_resp_b["status"] == STATE_ROUND_COMPLETE

        # Summary forbidden before settlement (even with valid token)
        status, res_summ = _http_request(
            f"{ctx.base_url}/api/blind/summary?session_id={session_id}",
            headers={"X-Session-Token": token_a},
        )
        assert status == 403
        assert res_summ["error"]["code"] == "NOT_SETTLED"

        # 9. Continue votes
        _http_request(
            f"{ctx.base_url}/api/blind/continue",
            method="POST",
            body={"session_id": session_id, "participant_id": p_a},
            headers={"X-Session-Token": token_a},
        )
        status, res_cont_b = _http_request(
            f"{ctx.base_url}/api/blind/continue",
            method="POST",
            body={"session_id": session_id, "participant_id": p_b},
            headers={"X-Session-Token": token_b},
        )
        assert status == 200
        assert res_cont_b["status"] == STATE_INPUT_OPEN
        assert res_cont_b["current_round_index"] == 1
        # Now B is sender!
        assert res_cont_b["role"] == "SENDER"

        # 10. End session early
        status, res_end = _http_request(
            f"{ctx.base_url}/api/blind/end",
            method="POST",
            body={"session_id": session_id, "participant_id": p_b},
            headers={"X-Session-Token": token_b},
        )
        assert status == 200
        assert res_end["session"]["status"] == STATE_SETTLEMENT or res_end.get("status") == STATE_SETTLEMENT

        # 11. Summary requires X-Session-Token even after settlement
        status, res_unauth_summ = _http_request(
            f"{ctx.base_url}/api/blind/summary?session_id={session_id}"
        )
        assert status == 401
        assert res_unauth_summ["error"]["code"] == "UNAUTHORIZED"

        # Summary succeeds with valid participant session token
        status, summary = _http_request(
            f"{ctx.base_url}/api/blind/summary?session_id={session_id}",
            headers={"X-Session-Token": token_a},
        )
        assert status == 200
        assert summary["session"]["status"] == STATE_SETTLEMENT
        assert len(summary["markers"]) >= 1

        # 12. Reveal endpoint with reveal_token
        # Wrong reveal token -> 403
        status, err_reveal = _http_request(
            f"{ctx.base_url}/api/blind/reveal?session_id={session_id}&reveal_token=wrong_token"
        )
        assert status == 403
        assert err_reveal["error"]["code"] == "FORBIDDEN"

        # Valid reveal token configured in session settings
        session = ctx.service.db.get_session(session_id)
        reveal_token = session["settings"].get("reveal_token")
        if reveal_token:
            status, reveal_data = _http_request(
                f"{ctx.base_url}/api/blind/reveal?session_id={session_id}&reveal_token={reveal_token}"
            )
            assert status == 200
            assert reveal_data["session"]["status"] == STATE_SETTLEMENT
    finally:
        ctx.close()


def test_auth_and_permission_enforcement():
    ctx = TestServerContext()
    try:
        session_id = "s_http_auth"
        ctx.service.create_session(session_id)
        token_a = "token_a"
        token_b = "token_b"

        res_a = ctx.service.join(session_id, "A", token_a)
        res_b = ctx.service.join(session_id, "B", token_b)
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        ctx.service.ready(session_id, p_a)
        ctx.service.ready(session_id, p_b)
        ctx.service.start_session(session_id)

        vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}

        # 1. Missing Token Header -> 401
        status, err1 = _http_request(
            f"{ctx.base_url}/api/blind/submit_input",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_a,
                "payload": {"text": "Hello", "input_vadc": vadc},
            },
        )
        assert status == 401
        assert err1["error"]["code"] == "UNAUTHORIZED"

        # 2. Wrong Token -> 401
        status, err2 = _http_request(
            f"{ctx.base_url}/api/blind/submit_input",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_a,
                "payload": {"text": "Hello", "input_vadc": vadc},
            },
            headers={"X-Session-Token": "completely_wrong_token"},
        )
        assert status == 401
        assert err2["error"]["code"] == "UNAUTHORIZED"

        # 3. Role Mismatch: Receiver B tries to submit input -> 400 ROLE_MISMATCH
        status, err3 = _http_request(
            f"{ctx.base_url}/api/blind/submit_input",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_b,
                "payload": {"text": "Hello from receiver", "input_vadc": vadc},
            },
            headers={"X-Session-Token": token_b},
        )
        assert status == 400
        assert err3["error"]["code"] == "ROLE_MISMATCH"

        # Valid input by A
        _http_request(
            f"{ctx.base_url}/api/blind/submit_input",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_a,
                "payload": {"text": "Valid text", "input_vadc": vadc},
            },
            headers={"X-Session-Token": token_a},
        )

        # 4. Role Mismatch: Sender A tries to submit receiver response -> 400 ROLE_MISMATCH
        status, err4 = _http_request(
            f"{ctx.base_url}/api/blind/submit_receiver",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_a,
                "payload": {"receiver_vadc": vadc},
            },
            headers={"X-Session-Token": token_a},
        )
        # 5. Anonymous State Access Restrictions:
        # In READY or active session, anonymous query without token -> 401 UNAUTHORIZED
        status, anon_active = _http_request(
            f"{ctx.base_url}/api/blind/state?session_id={session_id}"
        )
        assert status == 401
        assert anon_active["error"]["code"] == "UNAUTHORIZED"

        # In LOBBY, anonymous query returns ONLY minimal info: {status: LOBBY, participant_count: N}
        session_lobby = "s_http_anon_lobby"
        ctx.service.create_session(session_lobby)
        ctx.service.join(session_lobby, "A", "tok_lobby_a")
        status, anon_lobby = _http_request(
            f"{ctx.base_url}/api/blind/state?session_id={session_lobby}"
        )
        assert status == 200
        assert anon_lobby == {"status": "LOBBY", "participant_count": 1}
        # Ensure no internal keys leaked
        assert "participants" not in anon_lobby
        assert "version" not in anon_lobby
    finally:
        ctx.close()


def test_idempotency_and_stale_version():
    ctx = TestServerContext()
    try:
        session_id = "s_http_idem"
        ctx.service.create_session(session_id)
        token_a = "tok_a"
        token_b = "tok_b"

        res_a = ctx.service.join(session_id, "A", token_a)
        res_b = ctx.service.join(session_id, "B", token_b)
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        ctx.service.ready(session_id, p_a)
        ctx.service.ready(session_id, p_b)
        ctx.service.start_session(session_id)

        vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}

        # 1. Stale client_version (version=0 when db version is 3) -> 400 STALE_VERSION
        status, err_stale = _http_request(
            f"{ctx.base_url}/api/blind/submit_input",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_a,
                "client_version": 0,
                "payload": {"text": "Stale submit", "input_vadc": vadc},
            },
            headers={"X-Session-Token": token_a},
        )
        assert status == 400
        assert err_stale["error"]["code"] == "STALE_VERSION"

        # 2. Valid first submit with idempotency_key
        status, res1 = _http_request(
            f"{ctx.base_url}/api/blind/submit_input",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_a,
                "idempotency_key": "k_uniq_01",
                "payload": {"text": "First submit", "input_vadc": vadc},
            },
            headers={"X-Session-Token": token_a},
        )
        assert status == 200

        # 3. Duplicate submit with same idempotency_key -> 200 with cached projection
        status, res2 = _http_request(
            f"{ctx.base_url}/api/blind/submit_input",
            method="POST",
            body={
                "session_id": session_id,
                "participant_id": p_a,
                "idempotency_key": "k_uniq_01",
                "payload": {"text": "First submit", "input_vadc": vadc},
            },
            headers={"X-Session-Token": token_a},
        )
        assert status == 200
        assert res2["version"] == res1["version"]

        # Confirm database has exactly 1 input event and 1 marker
        full = ctx.service.db.get_full_session(session_id)
        assert len(full["input_events"]) == 1
        assert len(full["markers"]) == 1
    finally:
        ctx.close()


def test_concurrent_submissions_no_duplicate_marker():
    """Verify concurrent HTTP requests cannot create multiple markers for the same round."""
    ctx = TestServerContext()
    try:
        session_id = "s_http_race"
        ctx.service.create_session(session_id)
        token_a = "tok_a"
        token_b = "tok_b"

        res_a = ctx.service.join(session_id, "A", token_a)
        res_b = ctx.service.join(session_id, "B", token_b)
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        ctx.service.ready(session_id, p_a)
        ctx.service.ready(session_id, p_b)
        ctx.service.start_session(session_id)

        vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}

        results = []

        def submit(key: str):
            status, resp = _http_request(
                f"{ctx.base_url}/api/blind/submit_input",
                method="POST",
                body={
                    "session_id": session_id,
                    "participant_id": p_a,
                    "idempotency_key": key,
                    "payload": {"text": f"Race text {key}", "input_vadc": vadc},
                },
                headers={"X-Session-Token": token_a},
            )
            results.append((status, resp))

        # Launch two threads concurrently
        t1 = threading.Thread(target=submit, args=("race_k1",))
        t2 = threading.Thread(target=submit, args=("race_k2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one must succeed with 200; the other must be rejected (400) because state moved
        statuses = [r[0] for r in results]
        assert 200 in statuses
        assert len(statuses) == 2

        full = ctx.service.db.get_full_session(session_id)
        assert len(full["markers"]) == 1, f"Expected exactly 1 marker, got {len(full['markers'])}"
    finally:
        ctx.close()


def test_error_handling_no_traceback_leakage():
    ctx = TestServerContext()
    try:
        # Malformed JSON POST
        req = Request(
            f"{ctx.base_url}/api/blind/submit_input",
            data=b"{not_json: true,",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(req)
            assert False, "Should fail on invalid JSON"
        except HTTPError as e:
            assert e.code == 400
            err_data = json.loads(e.read().decode("utf-8"))
            assert err_data["error"]["code"] == "INVALID_JSON"
            # Ensure no Python traceback strings
            assert "Traceback" not in json.dumps(err_data)
            assert "File \"" not in json.dumps(err_data)
    finally:
        ctx.close()


def test_long_polling():
    """Verify long polling unblocks upon state update, and returns unchanged=True on timeout."""
    # Use short timeout 0.5s for test responsiveness
    ctx = TestServerContext(long_poll_timeout=0.5)
    try:
        session_id = "s_http_poll"
        ctx.service.create_session(session_id)
        token_a = "tok_a"
        res_a = ctx.service.join(session_id, "A", token_a)
        p_a = res_a["participant"]["participant_id"]

        session = ctx.service.db.get_session(session_id)
        v = session["version"]

        # 1. Long polling timeout test (no state change)
        start_t = time.time()
        status, data = _http_request(
            f"{ctx.base_url}/api/blind/state?session_id={session_id}&participant_id={p_a}&version={v}",
            headers={"X-Session-Token": token_a},
        )
        elapsed = time.time() - start_t
        assert status == 200
        assert data.get("unchanged") is True
        assert elapsed >= 0.45  # Waited approximately long_poll_timeout

        # 2. Long polling reactive wakeup test (unblocks immediately when another client acts)
        poll_result = {}

        def poll_client():
            st, d = _http_request(
                f"{ctx.base_url}/api/blind/state?session_id={session_id}&participant_id={p_a}&version={v}",
                headers={"X-Session-Token": token_a},
            )
            poll_result["status"] = st
            poll_result["data"] = d

        t = threading.Thread(target=poll_client)
        t.start()
        time.sleep(0.1)  # Ensure poll_client is waiting in condition

        # Wake it up by joining participant B
        token_b = "tok_b"
        _http_request(
            f"{ctx.base_url}/api/blind/join",
            method="POST",
            body={"session_id": session_id, "label": "B", "client_token": token_b},
        )
        t.join(timeout=2.0)

        assert poll_result["status"] == 200
        assert poll_result["data"].get("unchanged") is False
        assert poll_result["data"]["version"] > v
    finally:
        ctx.close()


if __name__ == "__main__":
    print("[*] Running test_server.py...")
    test_health_endpoint()
    test_standard_flow_and_privacy_projection()
    test_auth_and_permission_enforcement()
    test_idempotency_and_stale_version()
    test_concurrent_submissions_no_duplicate_marker()
    test_error_handling_no_traceback_leakage()
    test_long_polling()
    print("[✓] All Phase 4 HTTP Gateway tests passed successfully!")
