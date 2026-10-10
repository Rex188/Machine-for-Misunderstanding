"""
test_service.py — Exhaustive Integration Tests for Application Orchestrator
Tests:
- Complete 3-round interaction flow with FakeModelBackend and FakeOscTransport
- Failure isolation: Model failure creates NO marker and moves to ERROR
- Failure isolation: OSC failure creates NO marker and moves to ERROR
- Strict role and actor permission enforcement
- Duplicate idempotency key handling
- Stale client version rejection
- Early settlement by either participant
- Double-blind privacy projections (Receiver never sees sender text/VAD before settlement)
"""

import os
import shutil
import tempfile
from db import Database
from service import BlindTestService
from acoustic_bridge import FakeModelBackend, FakeOscTransport
from state_machine import (
    STATE_LOBBY,
    STATE_READY,
    STATE_INPUT_OPEN,
    STATE_RECEIVER_RESPONSE,
    STATE_ROUND_COMPLETE,
    STATE_SETTLEMENT,
    STATE_ERROR,
)


def setup_test_service(model_fail=False, osc_fail=False):
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_service.db")
    db = Database(db_path=db_path)
    db.init_db()

    model_backend = FakeModelBackend(should_fail=model_fail)
    osc_transport = FakeOscTransport(should_fail=osc_fail)
    service = BlindTestService(db=db, model_backend=model_backend, osc_transport=osc_transport)
    return service, temp_dir


def test_full_three_round_flow():
    """Verify complete 3-round flow, role swapping, and max-round settlement."""
    service, temp_dir = setup_test_service()
    try:
        # Create session
        sess = service.create_session("s_flow_01", max_rounds=3)
        assert sess["status"] == STATE_LOBBY

        # Join A and B
        res_a = service.join("s_flow_01", "A", "token_a")
        assert res_a["accepted"] is True
        res_b = service.join("s_flow_01", "B", "token_b")
        assert res_b["accepted"] is True

        # Ready A and B
        service.ready("s_flow_01", res_a["participant"]["participant_id"])
        service.ready("s_flow_01", res_b["participant"]["participant_id"])

        # Start session -> INPUT_OPEN (Round 0)
        res_start = service.start_session("s_flow_01")
        assert res_start["accepted"] is True
        assert res_start["session_status"] == STATE_INPUT_OPEN

        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]

        # ── ROUND 1 (Index 0: A is Sender, B is Receiver) ──
        in_vadc_1 = {"valence": 0.2, "arousal": 0.8, "dominance": 0.1, "confidence": 0.9}
        res_in1 = service.submit_input(
            "s_flow_01", p_a, "Cold winter air against the window.", in_vadc_1, "sub_1", idempotency_key="k_in_1"
        )
        assert res_in1["accepted"] is True
        assert res_in1["sequence"] == 1
        assert res_in1["session_status"] == STATE_RECEIVER_RESPONSE

        # Test duplicate idempotency key on submit_input
        dup_in1 = service.submit_input(
            "s_flow_01", p_a, "Cold winter air against the window.", in_vadc_1, "sub_1", idempotency_key="k_in_1"
        )
        assert dup_in1["accepted"] is True
        assert dup_in1["marker_id"] == res_in1["marker_id"]

        # Check Privacy Projection during Round 1
        proj_receiver = service.get_projection("s_flow_01", p_b)
        assert proj_receiver["role"] == "RECEIVER"
        assert "own_input" not in proj_receiver
        # Verify strictly masked
        assert "text" not in str(proj_receiver)
        assert "Cold winter air" not in str(proj_receiver)

        # Receiver B submits evaluation
        rec_vadc_1 = {"valence": 0.4, "arousal": 0.6, "dominance": 0.3, "confidence": 0.7}
        res_rec1 = service.submit_receiver_response(
            "s_flow_01", p_b, rec_vadc_1, "Felt sudden warmth.", listening_confirmed=True, idempotency_key="k_rec_1"
        )
        assert res_rec1["accepted"] is True
        assert res_rec1["session_status"] == STATE_ROUND_COMPLETE
        assert res_rec1["metrics"]["raw_distance"]["total"] > 0

        # Both vote to continue -> Advance to Round 2
        service.choose_continue("s_flow_01", p_a)
        res_cont1 = service.choose_continue("s_flow_01", p_b)
        assert res_cont1["accepted"] is True
        assert res_cont1["session_status"] == STATE_INPUT_OPEN
        assert res_cont1["round"]["round_index"] == 1
        assert res_cont1["round"]["sender_id"] == p_b  # Swapped!
        assert res_cont1["round"]["receiver_id"] == p_a

        # ── ROUND 2 (Index 1: B is Sender, A is Receiver) ──
        in_vadc_2 = {"valence": 0.5, "arousal": 0.4, "dominance": 0.6, "confidence": 0.8}
        res_in2 = service.submit_input("s_flow_01", p_b, "The warmth spread slowly.", in_vadc_2, "sub_2")
        assert res_in2["accepted"] is True
        assert res_in2["sequence"] == 2

        rec_vadc_2 = {"valence": 0.7, "arousal": 0.3, "dominance": 0.5, "confidence": 0.7}
        res_rec2 = service.submit_receiver_response("s_flow_01", p_a, rec_vadc_2, "Echoes of light.")
        assert res_rec2["accepted"] is True
        assert res_rec2["session_status"] == STATE_ROUND_COMPLETE
        # Round 2 must have non-null inter_round_drift!
        assert res_rec2["metrics"]["inter_round_drift"] is not None

        # Both vote to continue -> Advance to Round 3
        service.choose_continue("s_flow_01", p_b)
        res_cont2 = service.choose_continue("s_flow_01", p_a)
        assert res_cont2["accepted"] is True
        assert res_cont2["round"]["round_index"] == 2
        assert res_cont2["round"]["sender_id"] == p_a  # Swapped back to A!
        assert res_cont2["round"]["receiver_id"] == p_b

        # ── ROUND 3 (Index 2: A is Sender, B is Receiver, Max Rounds = 3) ──
        in_vadc_3 = {"valence": 0.8, "arousal": 0.2, "dominance": 0.9, "confidence": 0.9}
        res_in3 = service.submit_input("s_flow_01", p_a, "Final peaceful twilight.", in_vadc_3, "sub_3")
        assert res_in3["accepted"] is True
        assert res_in3["sequence"] == 3

        # Receiver B submits final evaluation -> Auto Transition to SETTLEMENT!
        rec_vadc_3 = {"valence": 0.85, "arousal": 0.25, "dominance": 0.8, "confidence": 0.85}
        res_rec3 = service.submit_receiver_response("s_flow_01", p_b, rec_vadc_3, "Complete stillness.")
        assert res_rec3["accepted"] is True
        assert res_rec3["session_status"] == STATE_SETTLEMENT

        # Verify revelation projection in settlement reveals full data
        proj_settle = service.get_projection("s_flow_01", p_a)
        assert len(proj_settle["rounds"]) == 3
        assert len(proj_settle["markers"]) == 3
        assert len(proj_settle["metrics"]) == 3
        assert "Cold winter air" in str(proj_settle)
    finally:
        shutil.rmtree(temp_dir)


def test_model_failure_creates_no_marker():
    """Verify that model failure transitions session to ERROR and creates zero markers."""
    service, temp_dir = setup_test_service(model_fail=True)
    try:
        service.create_session("s_fail_model")
        res_a = service.join("s_fail_model", "A", "tok_a")
        res_b = service.join("s_fail_model", "B", "tok_b")
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        service.ready("s_fail_model", p_a)
        service.ready("s_fail_model", p_b)
        service.start_session("s_fail_model")

        vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}
        res = service.submit_input("s_fail_model", p_a, "Failing text", vadc, "sub_f1")

        assert res["accepted"] is False
        assert "Model inference failed" in res["error"]

        # Verify session state is ERROR
        sess = service.db.get_session("s_fail_model")
        assert sess["status"] == STATE_ERROR

        # Verify NO MARKERS were created
        full = service.db.get_full_session("s_fail_model")
        assert len(full["markers"]) == 0
        assert len(full["input_events"]) == 0
    finally:
        shutil.rmtree(temp_dir)


def test_osc_failure_creates_no_marker():
    """Verify that OSC transport failure transitions session to ERROR and creates zero markers."""
    service, temp_dir = setup_test_service(osc_fail=True)
    try:
        service.create_session("s_fail_osc")
        res_a = service.join("s_fail_osc", "A", "tok_a")
        res_b = service.join("s_fail_osc", "B", "tok_b")
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        service.ready("s_fail_osc", p_a)
        service.ready("s_fail_osc", p_b)
        service.start_session("s_fail_osc")

        vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}
        res = service.submit_input("s_fail_osc", p_a, "Failing OSC text", vadc, "sub_f2")

        assert res["accepted"] is False
        assert "Acoustic update failed" in res["error"]

        # Verify session state is ERROR
        sess = service.db.get_session("s_fail_osc")
        assert sess["status"] == STATE_ERROR

        # Verify NO MARKERS were created
        full = service.db.get_full_session("s_fail_osc")
        assert len(full["markers"]) == 0
    finally:
        shutil.rmtree(temp_dir)


def test_invalid_model_output_creates_no_marker():
    """Verify that an invalid/out-of-range model output fails strictly without creating markers."""
    temp_dir = tempfile.mkdtemp()
    try:
        db = Database(db_path=os.path.join(temp_dir, "test.db"))
        db.init_db()
        # Model returning out-of-range valence
        invalid_model = FakeModelBackend(
            fixed_output={"valence": 1.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}
        )
        fake_osc = FakeOscTransport()
        service = BlindTestService(db, invalid_model, fake_osc)

        service.create_session("s_fail_model_val")
        res_a = service.join("s_fail_model_val", "A", "tok_a")
        res_b = service.join("s_fail_model_val", "B", "tok_b")
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        service.ready("s_fail_model_val", p_a)
        service.ready("s_fail_model_val", p_b)
        service.start_session("s_fail_model_val")

        vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}
        res = service.submit_input("s_fail_model_val", p_a, "Invalid model text", vadc, "sub_inv")

        assert res["accepted"] is False
        assert "Model output validation failed" in res["error"]

        # Verify session state is ERROR
        sess = service.db.get_session("s_fail_model_val")
        assert sess["status"] == STATE_ERROR

        # Verify NO MARKERS were created
        full = service.db.get_full_session("s_fail_model_val")
        assert len(full["markers"]) == 0
    finally:
        shutil.rmtree(temp_dir)


def test_permissions_and_stale_versions():
    """Verify actor permission rejections and stale versions."""
    service, temp_dir = setup_test_service()
    try:
        service.create_session("s_perm")
        res_a = service.join("s_perm", "A", "tok_a")
        res_b = service.join("s_perm", "B", "tok_b")
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        service.ready("s_perm", p_a)
        service.ready("s_perm", p_b)
        service.start_session("s_perm")

        vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}

        # Receiver B attempts to submit input during A's turn -> Rejected
        res_b_in = service.submit_input("s_perm", p_b, "Unauthorized", vadc, "sub_x")
        assert res_b_in["accepted"] is False
        assert "not the current sender" in res_b_in["reason"]

        # Sender A submits valid input
        service.submit_input("s_perm", p_a, "Authorized", vadc, "sub_ok")

        # Sender A attempts to submit receiver response -> Rejected
        res_a_rec = service.submit_receiver_response("s_perm", p_a, vadc, "Unauthorized response")
        assert res_a_rec["accepted"] is False
        assert "not the current receiver" in res_a_rec["reason"]

        # Stale client version test
        res_stale = service.submit_receiver_response(
            "s_perm", p_b, vadc, "Stale test", client_version=0
        )
        assert res_stale["accepted"] is False
        assert "Stale client version" in res_stale["reason"]
    finally:
        shutil.rmtree(temp_dir)


def test_early_settlement():
    """Verify that either participant can end the session early."""
    service, temp_dir = setup_test_service()
    try:
        service.create_session("s_early")
        res_a = service.join("s_early", "A", "tok_a")
        res_b = service.join("s_early", "B", "tok_b")
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        service.ready("s_early", p_a)
        service.ready("s_early", p_b)
        service.start_session("s_early")

        # Early termination by A
        res_end = service.end_session("s_early", p_a)
        assert res_end["accepted"] is True
        assert res_end["session_status"] == STATE_SETTLEMENT

        # Confirm DB shows settled
        sess = service.db.get_session("s_early")
        assert sess["status"] == STATE_SETTLEMENT
        assert sess["settled_at"] is not None
    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    print("[*] Running test_service.py...")
    test_full_three_round_flow()
    test_model_failure_creates_no_marker()
    test_osc_failure_creates_no_marker()
    test_invalid_model_output_creates_no_marker()
    test_permissions_and_stale_versions()
    test_early_settlement()
    print("[✓] All application orchestrator service tests passed successfully!")
