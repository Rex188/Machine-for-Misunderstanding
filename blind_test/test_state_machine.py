"""
test_state_machine.py — Exhaustive Verification Suite for Phase 2 State Machine
Tests all required scenarios:
1. Full Happy Path (3 rounds, role swapping, max-round auto settlement)
2. Strict Permission Enforcement (Actor authorization, Sender/Receiver role checks)
3. Re-entrancy, Stale Requests & Idempotency
4. All Termination Paths (Single-party end, Split votes, Timeout, Abort)
5. Error Transitions & Recovery Paths
"""

from state_machine import (
    StateMachine,
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
    EVENT_JOIN,
    EVENT_READY,
    EVENT_START_SESSION,
    EVENT_SUBMIT_INPUT,
    EVENT_MODEL_SUCCEEDED,
    EVENT_MODEL_FAILED,
    EVENT_ACOUSTIC_UPDATE_SUCCEEDED,
    EVENT_ACOUSTIC_UPDATE_FAILED,
    EVENT_SUBMIT_RECEIVER_RESPONSE,
    EVENT_CHOOSE_CONTINUE,
    EVENT_CHOOSE_END,
    EVENT_TIMEOUT,
    EVENT_RECOVER,
    EVENT_ABORT,
    SIDE_EFFECT_RUN_MODEL,
    SIDE_EFFECT_UPDATE_ACOUSTIC,
    SIDE_EFFECT_NOTIFY_RECEIVER,
    SIDE_EFFECT_COMPUTE_METRICS,
    SIDE_EFFECT_START_NEXT_ROUND,
    SIDE_EFFECT_SETTLE_SESSION,
    SIDE_EFFECT_RETRY_PREVIOUS,
)


def create_initial_snapshot(max_rounds=3):
    return {
        "session_id": "s_test_001",
        "status": STATE_LOBBY,
        "current_round_index": 0,
        "max_rounds": max_rounds,
        "version": 0,
        "participants": [],
        "rounds": [],
        "continuation_votes": {},
        "processed_idempotency_keys": {},
    }


# ── 1. Happy Path Test ────────────────────────────────────────────────────────

def test_full_happy_path_3_rounds():
    """Verify full 3-round execution, role swapping, and max-round settlement."""
    snap = create_initial_snapshot(max_rounds=3)

    # 1. Join Participant A
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_JOIN, actor_id="p_a", payload={"label": "A", "ready": True})
    assert res["accepted"] is True
    assert res["to_state"] == STATE_LOBBY
    snap = res["next_snapshot"]

    # 2. Join Participant B -> Both ready -> Transition to READY
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_JOIN, actor_id="p_b", payload={"label": "B", "ready": True})
    assert res["accepted"] is True
    assert res["to_state"] == STATE_READY
    snap = res["next_snapshot"]

    # 3. Start Session -> Transition to INPUT_OPEN (Round 0)
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_START_SESSION)
    assert res["accepted"] is True
    assert res["to_state"] == STATE_INPUT_OPEN
    assert res["round_index"] == 0
    assert res["sender_id"] == "p_a"
    assert res["receiver_id"] == "p_b"
    snap = res["next_snapshot"]

    # ── ROUND 1 (Index 0: A is Sender, B is Receiver) ──
    # Sender A submits input
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_SUBMIT_INPUT, actor_id="p_a", payload={"round_id": "r_s_test_001_1"})
    assert res["accepted"] is True
    assert res["to_state"] == STATE_MODEL_PROCESSING
    assert res["side_effect"] == SIDE_EFFECT_RUN_MODEL
    snap = res["next_snapshot"]

    # Model succeeds
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_MODEL_SUCCEEDED)
    assert res["accepted"] is True
    assert res["to_state"] == STATE_SOUND_UPDATE
    assert res["side_effect"] == SIDE_EFFECT_UPDATE_ACOUSTIC
    snap = res["next_snapshot"]

    # Acoustic update succeeds -> notify receiver
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_ACOUSTIC_UPDATE_SUCCEEDED)
    assert res["accepted"] is True
    assert res["to_state"] == STATE_RECEIVER_RESPONSE
    assert res["side_effect"] == SIDE_EFFECT_NOTIFY_RECEIVER
    snap = res["next_snapshot"]

    # Receiver B submits evaluation
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_SUBMIT_RECEIVER_RESPONSE, actor_id="p_b", payload={"round_id": "r_s_test_001_1"})
    assert res["accepted"] is True
    assert res["to_state"] == STATE_ROUND_COMPLETE
    assert res["side_effect"] == SIDE_EFFECT_COMPUTE_METRICS
    snap = res["next_snapshot"]

    # Both vote continue -> Advance to Round 2 (Index 1)
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_CHOOSE_CONTINUE, actor_id="p_a")
    assert res["accepted"] is True
    assert res["to_state"] == STATE_NEXT_ROUND_PENDING
    snap = res["next_snapshot"]

    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_CHOOSE_CONTINUE, actor_id="p_b")
    assert res["accepted"] is True
    assert res["to_state"] == STATE_INPUT_OPEN
    assert res["round_index"] == 1
    assert res["sender_id"] == "p_b"  # Role Swapped!
    assert res["receiver_id"] == "p_a"
    assert res["side_effect"] == SIDE_EFFECT_START_NEXT_ROUND
    snap = res["next_snapshot"]

    # ── ROUND 2 (Index 1: B is Sender, A is Receiver) ──
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_SUBMIT_INPUT, actor_id="p_b", payload={"round_id": "r_s_test_001_2"})
    assert res["accepted"] is True
    snap = res["next_snapshot"]

    sm = StateMachine(snap)
    snap = sm.dispatch(EVENT_MODEL_SUCCEEDED)["next_snapshot"]
    sm = StateMachine(snap)
    snap = sm.dispatch(EVENT_ACOUSTIC_UPDATE_SUCCEEDED)["next_snapshot"]

    # Receiver A submits evaluation
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_SUBMIT_RECEIVER_RESPONSE, actor_id="p_a", payload={"round_id": "r_s_test_001_2"})
    assert res["accepted"] is True
    assert res["to_state"] == STATE_ROUND_COMPLETE
    snap = res["next_snapshot"]

    # Both vote continue -> Advance to Round 3 (Index 2)
    sm = StateMachine(snap)
    snap = sm.dispatch(EVENT_CHOOSE_CONTINUE, actor_id="p_b")["next_snapshot"]
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_CHOOSE_CONTINUE, actor_id="p_a")
    assert res["accepted"] is True
    assert res["to_state"] == STATE_INPUT_OPEN
    assert res["round_index"] == 2
    assert res["sender_id"] == "p_a"  # Role Swapped back to A!
    assert res["receiver_id"] == "p_b"
    snap = res["next_snapshot"]

    # ── ROUND 3 (Index 2: Max Round reached) ──
    sm = StateMachine(snap)
    snap = sm.dispatch(EVENT_SUBMIT_INPUT, actor_id="p_a", payload={"round_id": "r_s_test_001_3"})["next_snapshot"]
    sm = StateMachine(snap)
    snap = sm.dispatch(EVENT_MODEL_SUCCEEDED)["next_snapshot"]
    sm = StateMachine(snap)
    snap = sm.dispatch(EVENT_ACOUSTIC_UPDATE_SUCCEEDED)["next_snapshot"]

    # Receiver B submits final evaluation -> Auto Transition to SETTLEMENT!
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_SUBMIT_RECEIVER_RESPONSE, actor_id="p_b", payload={"round_id": "r_s_test_001_3"})
    assert res["accepted"] is True
    assert res["to_state"] == STATE_SETTLEMENT
    assert res["side_effect"] == SIDE_EFFECT_SETTLE_SESSION
    snap = res["next_snapshot"]

    # Verify terminal status: further input is rejected
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_SUBMIT_INPUT, actor_id="p_a")
    assert res["accepted"] is False
    assert "terminal state" in res["reason"]


# ── 2. Permission Tests ───────────────────────────────────────────────────────

def test_permission_enforcement():
    """Verify unauthorized actors are rejected."""
    snap = {
        "session_id": "s_001",
        "status": STATE_INPUT_OPEN,
        "current_round_index": 0,
        "max_rounds": 3,
        "version": 1,
        "participants": [
            {"participant_id": "p_a", "label": "A"},
            {"participant_id": "p_b", "label": "B"},
        ],
        "rounds": [{"round_id": "r_1", "round_index": 0}],
    }

    # B attempts to submit input during A's turn as sender
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_SUBMIT_INPUT, actor_id="p_b")
    assert res["accepted"] is False
    assert "not the current sender" in res["reason"]

    # Unknown actor attempts to submit
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_SUBMIT_INPUT, actor_id="p_unknown")
    assert res["accepted"] is False

    # Move to RECEIVER_RESPONSE: A attempts to submit receiver response
    snap["status"] = STATE_RECEIVER_RESPONSE
    sm = StateMachine(snap)
    res = sm.dispatch(EVENT_SUBMIT_RECEIVER_RESPONSE, actor_id="p_a")
    assert res["accepted"] is False
    assert "not the current receiver" in res["reason"]


# ── 3. Duplicates, Stale Requests & Idempotency ──────────────────────────────

def test_idempotency_and_stale_requests():
    """Verify idempotency key deduplication and stale request rejection."""
    snap = {
        "session_id": "s_001",
        "status": STATE_INPUT_OPEN,
        "current_round_index": 0,
        "max_rounds": 3,
        "version": 5,
        "participants": [
            {"participant_id": "p_a", "label": "A"},
            {"participant_id": "p_b", "label": "B"},
        ],
        "rounds": [{"round_id": "r_1", "round_index": 0}],
        "processed_idempotency_keys": {},
    }

    # First submission with idempotency key
    sm = StateMachine(snap)
    res1 = sm.dispatch(
        EVENT_SUBMIT_INPUT,
        actor_id="p_a",
        payload={"idempotency_key": "key_submit_1", "client_version": 5},
    )
    assert res1["accepted"] is True
    assert res1["duplicate"] is False
    snap_after = res1["next_snapshot"]

    # Exact duplicate retry with same idempotency key
    sm2 = StateMachine(snap_after)
    res2 = sm2.dispatch(
        EVENT_SUBMIT_INPUT,
        actor_id="p_a",
        payload={"idempotency_key": "key_submit_1", "client_version": 5},
    )
    assert res2["accepted"] is True
    assert res2["duplicate"] is True
    assert res2["original_transition_id"] == res1["transition_id"]

    # Stale client version test
    sm3 = StateMachine(snap_after)  # version is now 6
    res3 = sm3.dispatch(
        EVENT_MODEL_SUCCEEDED,
        payload={"client_version": 2},  # older than 6
    )
    assert res3["accepted"] is False
    assert "Stale client version" in res3["reason"]

    # Stale round_id test
    snap["status"] = STATE_INPUT_OPEN
    sm4 = StateMachine(snap)
    res4 = sm4.dispatch(
        EVENT_SUBMIT_INPUT,
        actor_id="p_a",
        payload={"round_id": "old_round_999"},
    )
    assert res4["accepted"] is False
    assert "Stale round_id" in res4["reason"]


# ── 4. Termination Paths ──────────────────────────────────────────────────────

def test_termination_paths():
    """Verify various ways a session terminates into SETTLEMENT."""
    base_snap = {
        "session_id": "s_001",
        "status": STATE_ROUND_COMPLETE,
        "current_round_index": 0,
        "max_rounds": 3,
        "version": 10,
        "participants": [
            {"participant_id": "p_a", "label": "A"},
            {"participant_id": "p_b", "label": "B"},
        ],
        "rounds": [{"round_id": "r_1", "round_index": 0}],
    }

    # Scenario A: Sender A chooses end
    sm = StateMachine(base_snap)
    res = sm.dispatch(EVENT_CHOOSE_END, actor_id="p_a")
    assert res["accepted"] is True
    assert res["to_state"] == STATE_SETTLEMENT
    assert res["side_effect"] == SIDE_EFFECT_SETTLE_SESSION

    # Scenario B: Receiver B chooses end
    sm = StateMachine(base_snap)
    res = sm.dispatch(EVENT_CHOOSE_END, actor_id="p_b")
    assert res["accepted"] is True
    assert res["to_state"] == STATE_SETTLEMENT

    # Scenario C: Split vote (A votes continue, B votes end in NEXT_ROUND_PENDING)
    sm = StateMachine(base_snap)
    snap_pending = sm.dispatch(EVENT_CHOOSE_CONTINUE, actor_id="p_a")["next_snapshot"]
    assert snap_pending["status"] == STATE_NEXT_ROUND_PENDING

    sm_pending = StateMachine(snap_pending)
    res_split = sm_pending.dispatch(EVENT_CHOOSE_END, actor_id="p_b")
    assert res_split["accepted"] is True
    assert res_split["to_state"] == STATE_SETTLEMENT

    # Scenario D: Timeout in NEXT_ROUND_PENDING -> SETTLEMENT
    sm_timeout = StateMachine(snap_pending)
    res_timeout = sm_timeout.dispatch(EVENT_TIMEOUT)
    assert res_timeout["accepted"] is True
    assert res_timeout["to_state"] == STATE_SETTLEMENT

    # Scenario E: Abort from any state
    sm_abort = StateMachine(base_snap)
    res_abort = sm_abort.dispatch(EVENT_ABORT)
    assert res_abort["accepted"] is True
    assert res_abort["to_state"] == STATE_ABORTED


# ── 5. Error Recovery Paths ───────────────────────────────────────────────────

def test_error_and_recovery():
    """Verify failure states and recovery mechanics."""
    snap = {
        "session_id": "s_001",
        "status": STATE_MODEL_PROCESSING,
        "current_round_index": 0,
        "max_rounds": 3,
        "version": 4,
        "participants": [
            {"participant_id": "p_a", "label": "A"},
            {"participant_id": "p_b", "label": "B"},
        ],
        "rounds": [{"round_id": "r_1", "round_index": 0}],
    }

    # Model fails -> Transition to ERROR
    sm = StateMachine(snap)
    res_fail = sm.dispatch(EVENT_MODEL_FAILED)
    assert res_fail["accepted"] is True
    assert res_fail["to_state"] == STATE_ERROR
    snap_err = res_fail["next_snapshot"]
    assert snap_err["last_recoverable_state"] == STATE_MODEL_PROCESSING

    # Recover -> Transition back to MODEL_PROCESSING with RETRY side effect
    sm_rec = StateMachine(snap_err)
    res_rec = sm_rec.dispatch(EVENT_RECOVER)
    assert res_rec["accepted"] is True
    assert res_rec["to_state"] == STATE_MODEL_PROCESSING
    assert res_rec["side_effect"] == SIDE_EFFECT_RETRY_PREVIOUS

    # Acoustic update failure and recovery
    snap["status"] = STATE_SOUND_UPDATE
    sm_ac = StateMachine(snap)
    snap_ac_err = sm_ac.dispatch(EVENT_ACOUSTIC_UPDATE_FAILED)["next_snapshot"]
    assert snap_ac_err["status"] == STATE_ERROR
    assert snap_ac_err["last_recoverable_state"] == STATE_SOUND_UPDATE

    sm_ac_rec = StateMachine(snap_ac_err)
    res_ac_rec = sm_ac_rec.dispatch(EVENT_RECOVER)
    assert res_ac_rec["accepted"] is True
    assert res_ac_rec["to_state"] == STATE_SOUND_UPDATE

    # Error -> Abort
    sm_err_abort = StateMachine(snap_ac_err)
    res_err_abort = sm_err_abort.dispatch(EVENT_ABORT)
    assert res_err_abort["accepted"] is True
    assert res_err_abort["to_state"] == STATE_ABORTED


if __name__ == "__main__":
    print("[*] Running all state machine tests...")
    test_full_happy_path_3_rounds()
    test_permission_enforcement()
    test_idempotency_and_stale_requests()
    test_termination_paths()
    test_error_and_recovery()
    print("[✓] All Phase 2 State Machine test suites passed successfully!")
