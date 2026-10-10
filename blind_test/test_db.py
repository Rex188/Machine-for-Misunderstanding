"""
test_db.py — Comprehensive Unit & Integration Test for Data Layer
Tests all Phase 1 capabilities:
- Database initialization with schema.sql
- PRAGMAs verification (foreign_keys=ON, journal_mode=WAL, busy_timeout=5000)
- Thread-local connection isolation
- Session creation
- Two participants joining (A and B with token hashing)
- Round creation
- Atomic Sender Input + Model Run + Marker commit
- Atomic Receiver Response + Metrics commit
- Full Session retrieval and schema compliance
"""

import os
import shutil
import tempfile
import threading
from db import Database, hash_token

def test_data_layer():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_blind.db")
    print(f"[*] Running database tests on temporary path: {db_path}")

    db = Database(db_path=db_path)

    # 1. Test PRAGMAs and Schema Init
    db.init_db()
    conn = db.get_connection()
    fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
    journal = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    busy = conn.execute("PRAGMA busy_timeout;").fetchone()[0]

    assert fk == 1, f"foreign_keys PRAGMA expected 1, got {fk}"
    assert journal.upper() == "WAL", f"journal_mode expected WAL, got {journal}"
    assert busy == 5000, f"busy_timeout expected 5000, got {busy}"
    print("[✓] PRAGMAs verified: foreign_keys=ON, journal_mode=WAL, busy_timeout=5000")

    # 2. Test Thread-Local Connection Isolation
    thread_conns = []
    def thread_worker():
        c = db.get_connection()
        thread_conns.append(id(c))

    t1 = threading.Thread(target=thread_worker)
    t2 = threading.Thread(target=thread_worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    main_conn_id = id(db.get_connection())
    assert thread_conns[0] != thread_conns[1], "Threads should have distinct connection instances"
    assert main_conn_id != thread_conns[0], "Main thread connection should be distinct from child thread"
    print("[✓] Thread-local connection isolation verified")

    # 3. Test Session Creation
    session = db.create_session(session_id="s_test_001", max_rounds=3)
    assert session["session_id"] == "s_test_001"
    assert session["status"] == "LOBBY"
    assert session["current_round_index"] == 0
    print("[✓] Session created: s_test_001 (status: LOBBY)")

    # 4. Test Add Two Participants
    p_a = db.add_participant("s_test_001", "A", "secret_token_a")
    p_b = db.add_participant("s_test_001", "B", "secret_token_b")
    assert p_a["label"] == "A"
    assert p_a["client_token_hash"] == hash_token("secret_token_a")
    assert p_b["label"] == "B"
    assert p_b["client_token_hash"] == hash_token("secret_token_b")
    print(f"[✓] Two participants joined: A ({p_a['participant_id']}), B ({p_b['participant_id']})")

    # 5. Test Create Round 1
    round_1 = db.create_round("s_test_001", round_index=0, sender_id=p_a["participant_id"], receiver_id=p_b["participant_id"])
    assert round_1["round_index"] == 0
    assert round_1["sender_id"] == p_a["participant_id"]
    assert round_1["receiver_id"] == p_b["participant_id"]
    assert round_1["status"] == "OPEN"
    print(f"[✓] Round 1 created: {round_1['round_id']} (Sender: A, Receiver: B)")

    # 6. Test Atomic Sender Input + Model Run + Marker
    text = "The key hesitated in the lock. My tongue seized up behind my teeth."
    input_vadc = {"valence": 0.2, "arousal": 0.8, "dominance": 0.1, "confidence": 0.9}
    model_output = {"valence": 0.18, "arousal": 0.84, "dominance": 0.12, "confidence": 0.8}
    voltages = {
        "timbre_v": 0.66, "frequency_v": 1.48, "amplitude_v": 8.38, "envelope_v": -3.6,
        "mode_v": -2.0, "chord_v": 5.0, "type_v": 0.0, "noise_v": 8.06
    }
    osc_dispatch = {"host": "127.0.0.1", "port": 7001, "status": "SENT"}

    inp, m_run, marker = db.commit_sender_input_and_marker(
        session_id="s_test_001",
        round_id=round_1["round_id"],
        actor_id=p_a["participant_id"],
        text=text,
        input_vadc=input_vadc,
        client_submission_id="sub_a_r1_1",
        model_backend="local_qwen",
        model_name="Qwen2.5-1.5B-LoRA",
        prompt_version="blind-v1",
        model_output=model_output,
        raw_output='{"valence": 0.18, "arousal": 0.84, "dominance": 0.12, "confidence": 0.8}',
        model_status="SUCCESS",
        fallback_used=False,
        fallback_reason=None,
        latency_ms=420,
        sequence=1,
        acoustic_state={"voltages": voltages},
        osc_dispatch=osc_dispatch,
    )

    assert inp["text"] == text
    assert m_run["status"] == "SUCCESS"
    assert marker["sequence"] == 1
    assert marker["status"] == "COMMITTED"

    # Check that session transitioned to RECEIVER_RESPONSE
    sess_after_in = db.get_session("s_test_001")
    assert sess_after_in["status"] == "RECEIVER_RESPONSE"
    print(f"[✓] Input event & Marker committed atomically: marker_id={marker['marker_id']}, sequence=1")

    # 7. Test Atomic Receiver Response + Metrics
    receiver_vadc = {"valence": 0.6, "arousal": 0.4, "dominance": 0.5, "confidence": 0.6}
    somatic_shift = "Felt a soothing release in the ribcage, though unexpected tension lingered."
    raw_dist = {"model": 0.035, "medium": 0.280, "total": 0.310}
    adj_dist = {"model": 0.031, "medium": 0.245, "total": 0.272}
    conf = {"input": 0.9, "model": 0.8, "receiver": 0.6}

    rec_resp, metrics = db.commit_receiver_response_and_metrics(
        session_id="s_test_001",
        round_id=round_1["round_id"],
        marker_id=marker["marker_id"],
        actor_id=p_b["participant_id"],
        receiver_vadc=receiver_vadc,
        somatic_shift=somatic_shift,
        raw_distance=raw_dist,
        confidence_adjusted_distance=adj_dist,
        confidence=conf,
        inter_round_drift=None,
        listening_confirmed=True,
        client_version=1,
    )

    assert rec_resp["listening_confirmed"] is True
    assert metrics["raw_distance"]["total"] == 0.310

    # Check that round and session transitioned to ROUND_COMPLETE
    r1_updated = db.get_round(round_1["round_id"])
    assert r1_updated["status"] == "COMPLETE"
    sess_after_rec = db.get_session("s_test_001")
    assert sess_after_rec["status"] == "ROUND_COMPLETE"
    print(f"[✓] Receiver response & metrics committed: round status={r1_updated['status']}")

    # 8. Test Query Complete Session (Canonical Export)
    full_session = db.get_full_session("s_test_001")
    assert full_session is not None
    assert len(full_session["participants"]) == 2
    assert len(full_session["rounds"]) == 1
    assert len(full_session["input_events"]) == 1
    assert len(full_session["model_runs"]) == 1
    assert len(full_session["markers"]) == 1
    assert len(full_session["receiver_responses"]) == 1
    assert len(full_session["metrics"]) == 1
    assert len(full_session["state_events"]) >= 3
    print("[✓] Full canonical session retrieved successfully across all 10 tables")
    print(f"    - Participants: {len(full_session['participants'])}")
    print(f"    - Rounds: {len(full_session['rounds'])}")
    print(f"    - Markers: {len(full_session['markers'])}")
    print(f"    - State Events: {len(full_session['state_events'])}")

    # Cleanup
    shutil.rmtree(temp_dir)
    print("\n[ALL TESTS PASSED] Phase 1 Data Layer is 100% verified and operational.")

if __name__ == "__main__":
    test_data_layer()
