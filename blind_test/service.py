"""
service.py — Application Orchestrator & Experiment Service
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Architecture:
- Coordinates Database (db.py), StateMachine (state_machine.py), Metrics (metrics.py),
  and AcousticBridge (acoustic_bridge.py).
- External Model and OSC dispatches execute strictly OUTSIDE SQLite transactions.
- Zero committed markers created upon failed model or OSC dispatch.
- Strict double-blind privacy projections: Receiver never sees sender text, input VADC,
  or model VADC prior to session settlement.
- Deduplication: Duplicate idempotency keys return cached results.
"""

from datetime import datetime
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from db import Database, utc_now_iso
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
)
from metrics import validate_vadc, calculate_round_metrics
from acoustic_bridge import (
    ModelBackend,
    OscTransport,
    FakeModelBackend,
    FakeOscTransport,
    compute_voltages,
)


class BlindTestService:
    """
    Authoritative Application Service.
    Orchestrates business operations, external calls, state transitions, and database commits.
    """

    def __init__(
        self,
        db: Database,
        model_backend: Optional[ModelBackend] = None,
        osc_transport: Optional[OscTransport] = None,
    ):
        self.db = db
        self.model_backend = model_backend or FakeModelBackend()
        self.osc_transport = osc_transport or FakeOscTransport()
        # In-memory session idempotency cache: {session_id: {idempotency_key: cached_result}}
        self._idempotency_cache: Dict[str, Dict[str, Any]] = {}

    def _build_snapshot(self, session_id: str) -> Dict[str, Any]:
        """Build an authoritative state snapshot for StateMachine evaluation."""
        session = self.db.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found")
        participants = self.db.get_participants(session_id)
        rounds = self.db.get_rounds(session_id)
        cached_keys = self._idempotency_cache.get(session_id, {})

        return {
            "session_id": session["session_id"],
            "status": session["status"],
            "current_round_index": session["current_round_index"],
            "max_rounds": session["max_rounds"],
            "version": session["version"],
            "participants": participants,
            "rounds": rounds,
            "continuation_votes": session.get("continuation_votes", {}),
            "processed_idempotency_keys": cached_keys,
        }

    # ── Session Lifecycle ─────────────────────────────────────────────────────

    def create_session(
        self,
        session_id: Optional[str] = None,
        max_rounds: int = 3,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new experiment session in LOBBY state."""
        return self.db.create_session(session_id=session_id, max_rounds=max_rounds, settings=settings)

    def join(self, session_id: str, label: str, client_token: str) -> Dict[str, Any]:
        """Participant joins session with chosen role label ('A' or 'B')."""
        snap = self._build_snapshot(session_id)
        sm = StateMachine(snap)
        actor_id = f"p_{session_id}_{label}"

        res = sm.dispatch(EVENT_JOIN, actor_id=actor_id, payload={"label": label, "ready": False})
        if not res["accepted"]:
            return {"accepted": False, "reason": res["reason"]}

        # Add participant to DB
        participant = self.db.add_participant(session_id, label, client_token, participant_id=actor_id)
        # Update session status if state machine advanced
        if res["to_state"] != snap["status"]:
            self.db.update_session_status(session_id, res["to_state"], actor_id=actor_id, event_type=EVENT_JOIN)

        return {"accepted": True, "participant": participant, "session_status": res["to_state"]}

    def ready(self, session_id: str, actor_id: str) -> Dict[str, Any]:
        """Mark participant as ready."""
        conn = self.db.get_connection()
        now = utc_now_iso()
        with conn:
            conn.execute(
                "UPDATE participants SET ready = 1, last_seen_at = ? WHERE participant_id = ?",
                (now, actor_id),
            )

        snap = self._build_snapshot(session_id)
        sm = StateMachine(snap)
        res = sm.dispatch(EVENT_READY, actor_id=actor_id)

        if res["accepted"]:
            if res["to_state"] != snap["status"]:
                self.db.update_session_status(session_id, res["to_state"], actor_id=actor_id, event_type=EVENT_READY)
            else:
                with conn:
                    conn.execute(
                        "UPDATE sessions SET version = version + 1, updated_at = ? WHERE session_id = ?",
                        (now, session_id),
                    )

        return {"accepted": True, "session_status": res["to_state"]}

    def start_session(self, session_id: str) -> Dict[str, Any]:
        """Start session and open Round 1 (Round index 0)."""
        snap = self._build_snapshot(session_id)
        sm = StateMachine(snap)
        res = sm.dispatch(EVENT_START_SESSION)
        if not res["accepted"]:
            return {"accepted": False, "reason": res["reason"]}

        # Determine initial roles (Round 0: A is Sender, B is Receiver)
        s_id, r_id = StateMachine.get_role_assignments(snap["participants"], 0)
        round_1 = self.db.create_round(session_id, round_index=0, sender_id=s_id, receiver_id=r_id)
        self.db.update_session_status(session_id, STATE_INPUT_OPEN, event_type=EVENT_START_SESSION)

        return {"accepted": True, "round": round_1, "session_status": STATE_INPUT_OPEN}

    # ── Sender Input & Marker Creation ────────────────────────────────────────

    def submit_input(
        self,
        session_id: str,
        actor_id: str,
        text: str,
        input_vadc: Dict[str, Any],
        client_submission_id: str,
        client_version: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sender submits somatic text and self-assessment VADC.
        External Model and OSC operations run OUTSIDE the SQLite transaction.
        Commits exactly one marker upon complete success.
        """
        # 1. Check idempotency cache first
        if idempotency_key and idempotency_key in self._idempotency_cache.get(session_id, {}):
            return self._idempotency_cache[session_id][idempotency_key]

        # 2. Validate input VADC
        try:
            coords, conf = validate_vadc(input_vadc, "input_vadc")
        except ValueError as e:
            return {"accepted": False, "reason": str(e)}

        snap = self._build_snapshot(session_id)
        curr_round_index = snap["current_round_index"]
        rounds = snap["rounds"]
        curr_round = next((r for r in rounds if r.get("round_index") == curr_round_index), None)
        if not curr_round:
            return {"accepted": False, "reason": f"Active round for index {curr_round_index} not found."}
        round_id = curr_round["round_id"]

        # 3. State Machine pre-check
        sm = StateMachine(snap)
        dispatch_payload = {
            "round_id": round_id,
            "client_version": client_version,
            "idempotency_key": idempotency_key,
        }
        res = sm.dispatch(EVENT_SUBMIT_INPUT, actor_id=actor_id, payload=dispatch_payload)
        if not res["accepted"]:
            return {"accepted": False, "reason": res["reason"]}
        if res.get("duplicate"):
            return res

        # 4. External Model Call (OUTSIDE SQLite transaction)
        model_res = self.model_backend.infer(text)
        if model_res.status != "SUCCESS" or not model_res.output:
            # Model failed -> update session to ERROR, NO MARKER COMMITTED
            self.db.update_session_status(session_id, STATE_ERROR, actor_id=actor_id, event_type=EVENT_MODEL_FAILED)
            return {
                "accepted": False,
                "error": "Model inference failed",
                "model_status": model_res.status,
                "fallback_reason": model_res.fallback_reason,
            }

        # 4b. Strict validation of model output before voltage computation
        try:
            validate_vadc(model_res.output, "model_output")
            voltages = compute_voltages(model_res.output, strict=True)
        except ValueError as e:
            self.db.update_session_status(session_id, STATE_ERROR, actor_id=actor_id, event_type=EVENT_MODEL_FAILED)
            return {
                "accepted": False,
                "error": f"Model output validation failed: {e}",
                "model_status": "INVALID_OUTPUT",
                "fallback_reason": str(e),
            }

        # 5. External OSC Call (OUTSIDE SQLite transaction)
        osc_res = self.osc_transport.send_voltages(voltages)
        if osc_res.status != "SENT":
            # OSC failed -> update session to ERROR, NO MARKER COMMITTED
            self.db.update_session_status(session_id, STATE_ERROR, actor_id=actor_id, event_type=EVENT_ACOUSTIC_UPDATE_FAILED)
            return {
                "accepted": False,
                "error": "Acoustic update failed",
                "osc_error": osc_res.error,
            }

        # 6. Commit Atomic Database Transaction (Input Event + Model Run + Marker)
        sequence = curr_round_index + 1
        input_event, model_run, marker = self.db.commit_sender_input_and_marker(
            session_id=session_id,
            round_id=round_id,
            actor_id=actor_id,
            text=text,
            input_vadc=input_vadc,
            client_submission_id=client_submission_id,
            model_backend=model_res.backend,
            model_name=model_res.model_name,
            prompt_version=model_res.prompt_version,
            model_output=model_res.output,
            raw_output=model_res.raw_output,
            model_status=model_res.status,
            fallback_used=model_res.fallback_used,
            fallback_reason=model_res.fallback_reason,
            latency_ms=model_res.latency_ms,
            sequence=sequence,
            acoustic_state={"voltages": voltages},
            osc_dispatch=osc_res.to_dict(),
        )

        result = {
            "accepted": True,
            "duplicate": False,
            "session_status": STATE_RECEIVER_RESPONSE,
            "round_id": round_id,
            "marker_id": marker["marker_id"],
            "sequence": sequence,
        }

        # Cache for idempotency
        if idempotency_key:
            self._idempotency_cache.setdefault(session_id, {})[idempotency_key] = result

        return result

    # ── Receiver Response & Metrics ──────────────────────────────────────────

    def submit_receiver_response(
        self,
        session_id: str,
        actor_id: str,
        receiver_vadc: Dict[str, Any],
        somatic_shift: str,
        listening_confirmed: bool = True,
        client_version: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Receiver submits perceived VADC and felt somatic shift.
        Computes deterministic metrics and completes current round.
        """
        # 1. Check idempotency cache first
        if idempotency_key and idempotency_key in self._idempotency_cache.get(session_id, {}):
            return self._idempotency_cache[session_id][idempotency_key]

        # 2. Validate receiver VADC
        try:
            coords, conf = validate_vadc(receiver_vadc, "receiver_vadc")
        except ValueError as e:
            return {"accepted": False, "reason": str(e)}

        snap = self._build_snapshot(session_id)
        curr_round_index = snap["current_round_index"]
        rounds = snap["rounds"]
        curr_round = next((r for r in rounds if r.get("round_index") == curr_round_index), None)
        if not curr_round or not curr_round.get("marker_id"):
            return {"accepted": False, "reason": "No committed acoustic marker found for current round."}

        round_id = curr_round["round_id"]
        marker_id = curr_round["marker_id"]

        # 3. State Machine pre-check
        sm = StateMachine(snap)
        dispatch_payload = {
            "round_id": round_id,
            "client_version": client_version,
            "idempotency_key": idempotency_key,
        }
        res = sm.dispatch(EVENT_SUBMIT_RECEIVER_RESPONSE, actor_id=actor_id, payload=dispatch_payload)
        if not res["accepted"]:
            return {"accepted": False, "reason": res["reason"]}
        if res.get("duplicate"):
            return res

        # 4. Fetch sender input and model outputs to calculate metrics
        input_event = self.db.get_input_event(curr_round["input_event_id"])
        model_run = self.db.get_model_run(curr_round["model_run_id"])
        if not input_event or not model_run:
            return {"accepted": False, "reason": "Failed to retrieve input event or model run for metrics."}

        # Check for previous receiver vadc (inter-round drift)
        prev_receiver_vadc = None
        if curr_round_index > 0:
            prev_round = next((r for r in rounds if r.get("round_index") == curr_round_index - 1), None)
            if prev_round and prev_round.get("receiver_response_id"):
                prev_resp = self.db.get_receiver_response(prev_round["receiver_response_id"])
                if prev_resp:
                    prev_receiver_vadc = prev_resp["receiver_vadc"]

        # 5. Compute deterministic metrics
        metrics_dict = calculate_round_metrics(
            input_vadc=input_event["input_vadc"],
            model_vadc=model_run["output"],
            receiver_vadc=receiver_vadc,
            previous_receiver_vadc=prev_receiver_vadc,
        )

        # 6. Commit Receiver Response + Metrics atomically
        resp_obj, metrics_obj = self.db.commit_receiver_response_and_metrics(
            session_id=session_id,
            round_id=round_id,
            marker_id=marker_id,
            actor_id=actor_id,
            receiver_vadc=receiver_vadc,
            somatic_shift=somatic_shift,
            raw_distance=metrics_dict["raw_distance"],
            confidence_adjusted_distance=metrics_dict["confidence_adjusted_distance"],
            confidence=metrics_dict["confidence"],
            inter_round_drift=metrics_dict["inter_round_drift"],
            listening_confirmed=listening_confirmed,
            formula_version=metrics_dict["formula_version"],
        )

        # 7. Check if StateMachine automatically settled session (max rounds reached)
        if res["to_state"] == STATE_SETTLEMENT:
            self.db.update_session_status(session_id, STATE_SETTLEMENT, actor_id=actor_id, event_type="MAX_ROUNDS_SETTLED")

        result = {
            "accepted": True,
            "duplicate": False,
            "session_status": res["to_state"],
            "round_id": round_id,
            "metrics": metrics_obj,
        }

        if idempotency_key:
            self._idempotency_cache.setdefault(session_id, {})[idempotency_key] = result

        return result

    # ── Continuation & Settlement ─────────────────────────────────────────────

    def choose_continue(self, session_id: str, actor_id: str) -> Dict[str, Any]:
        """Participant votes to advance to the next round."""
        snap = self._build_snapshot(session_id)
        sm = StateMachine(snap)
        res = sm.dispatch(EVENT_CHOOSE_CONTINUE, actor_id=actor_id)
        if not res["accepted"]:
            return {"accepted": False, "reason": res["reason"]}

        # Record vote
        votes = self.db.set_continuation_vote(session_id, actor_id, "continue")

        # If both agreed and state machine moved to INPUT_OPEN, create next round container
        if res["to_state"] == STATE_INPUT_OPEN:
            new_round_index = res["round_index"]
            new_s_id = res["sender_id"]
            new_r_id = res["receiver_id"]
            new_round = self.db.create_round(
                session_id, round_index=new_round_index, sender_id=new_s_id, receiver_id=new_r_id
            )
            self.db.reset_continuation_votes(session_id)
            self.db.update_session_status(session_id, STATE_INPUT_OPEN, actor_id=actor_id, event_type="NEXT_ROUND_STARTED")
            return {
                "accepted": True,
                "session_status": STATE_INPUT_OPEN,
                "round": new_round,
                "votes": {},
            }
        else:
            self.db.update_session_status(session_id, STATE_NEXT_ROUND_PENDING, actor_id=actor_id, event_type=EVENT_CHOOSE_CONTINUE)
            return {
                "accepted": True,
                "session_status": STATE_NEXT_ROUND_PENDING,
                "votes": votes,
            }

    def end_session(self, session_id: str, actor_id: Optional[str] = None) -> Dict[str, Any]:
        """Terminate dialogue and transition immediately to SETTLEMENT."""
        snap = self._build_snapshot(session_id)
        sm = StateMachine(snap)
        res = sm.dispatch(EVENT_CHOOSE_END, actor_id=actor_id)
        if not res["accepted"]:
            return {"accepted": False, "reason": res["reason"]}

        now = utc_now_iso()
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                "UPDATE sessions SET status = 'SETTLEMENT', settled_at = ?, updated_at = ? WHERE session_id = ?",
                (now, now, session_id),
            )
        self.db.update_session_status(session_id, STATE_SETTLEMENT, actor_id=actor_id, event_type=EVENT_CHOOSE_END)
        return {"accepted": True, "session_status": STATE_SETTLEMENT}

    # ── Privacy-Aware Projections ─────────────────────────────────────────────

    def get_projection(self, session_id: str, actor_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Return role-specific, privacy-sanitized view matching Section 14 of
        BLIND_TEST_DATA_SCHEMA.md.
        Receiver strictly CANNOT see sender text, input VAD, or model VAD before settlement.
        """
        session = self.db.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found")

        status = session["status"]
        participants = self.db.get_participants(session_id)
        current_round_index = session["current_round_index"]
        rounds = self.db.get_rounds(session_id)

        # If SETTLEMENT or ABORTED, return complete unmasked revelation
        if status in (STATE_SETTLEMENT, STATE_ABORTED):
            return self.db.get_full_session(session_id)

        # Active Progression: Identify role in current round
        sender_id, receiver_id = StateMachine.get_role_assignments(participants, current_round_index)

        # Base metadata shared by all
        projection = {
            "session_id": session_id,
            "status": status,
            "current_round_index": current_round_index,
            "max_rounds": session["max_rounds"],
            "version": session["version"],
            "participants": [{"participant_id": p["participant_id"], "label": p["label"], "ready": bool(p["ready"])} for p in participants],
        }

        curr_round = next((r for r in rounds if r.get("round_index") == current_round_index), None)

        if actor_id == sender_id:
            projection["role"] = "SENDER"
            if curr_round and curr_round.get("input_event_id"):
                inp = self.db.get_input_event(curr_round["input_event_id"])
                projection["own_input"] = {
                    "text": inp["text"],
                    "input_vadc": inp["input_vadc"],
                }
            projection["acoustic_status"] = "ACTIVE" if (curr_round and curr_round.get("marker_id")) else "WAITING"

        elif actor_id == receiver_id:
            projection["role"] = "RECEIVER"
            # Strict Privacy: ZERO access to sender text, input VAD, model VAD
            projection["acoustic_status"] = "ACTIVE" if (curr_round and curr_round.get("marker_id")) else "WAITING"
            projection["can_respond"] = (status == STATE_RECEIVER_RESPONSE)

        else:
            projection["role"] = "OBSERVER"

        return projection
