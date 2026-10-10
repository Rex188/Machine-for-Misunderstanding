"""
state_machine.py — Authoritative, Pure Experiment State Machine
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Design Principles:
- PURE functional logic: operates on an immutable snapshot, produces transition result + next snapshot.
- ZERO external I/O: No SQLite, No HTTP, No LLM, No OSC/VCV, No frontend logic.
- 11 Authoritative States matching BLIND_TEST_STATE_MACHINE.md.
- Strict Invariant Verification: Actor permissions, Round constraints, Idempotency, Max-round bounds.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple

# ── 11 Authoritative States ──────────────────────────────────────────────────
STATE_LOBBY = "LOBBY"
STATE_READY = "READY"
STATE_INPUT_OPEN = "INPUT_OPEN"
STATE_MODEL_PROCESSING = "MODEL_PROCESSING"
STATE_SOUND_UPDATE = "SOUND_UPDATE"
STATE_RECEIVER_RESPONSE = "RECEIVER_RESPONSE"
STATE_ROUND_COMPLETE = "ROUND_COMPLETE"
STATE_NEXT_ROUND_PENDING = "NEXT_ROUND_PENDING"
STATE_SETTLEMENT = "SETTLEMENT"
STATE_ERROR = "ERROR"
STATE_ABORTED = "ABORTED"

ALL_STATES: Set[str] = {
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
}

TERMINAL_STATES: Set[str] = {STATE_SETTLEMENT, STATE_ABORTED}

# ── Authoritative Events ─────────────────────────────────────────────────────
EVENT_JOIN = "JOIN"
EVENT_READY = "READY"
EVENT_START_SESSION = "START_SESSION"
EVENT_SUBMIT_INPUT = "SUBMIT_INPUT"
EVENT_MODEL_SUCCEEDED = "MODEL_SUCCEEDED"
EVENT_MODEL_FAILED = "MODEL_FAILED"
EVENT_ACOUSTIC_UPDATE_SUCCEEDED = "ACOUSTIC_UPDATE_SUCCEEDED"
EVENT_ACOUSTIC_UPDATE_FAILED = "ACOUSTIC_UPDATE_FAILED"
EVENT_SUBMIT_RECEIVER_RESPONSE = "SUBMIT_RECEIVER_RESPONSE"
EVENT_CHOOSE_CONTINUE = "CHOOSE_CONTINUE"
EVENT_CHOOSE_END = "CHOOSE_END"
EVENT_TIMEOUT = "TIMEOUT"
EVENT_RECOVER = "RECOVER"
EVENT_ABORT = "ABORT"

# ── Side Effects Requested by State Machine ──────────────────────────────────
SIDE_EFFECT_RUN_MODEL = "RUN_MODEL"
SIDE_EFFECT_UPDATE_ACOUSTIC = "UPDATE_ACOUSTIC"
SIDE_EFFECT_NOTIFY_RECEIVER = "NOTIFY_RECEIVER"
SIDE_EFFECT_COMPUTE_METRICS = "COMPUTE_METRICS"
SIDE_EFFECT_START_NEXT_ROUND = "START_NEXT_ROUND"
SIDE_EFFECT_SETTLE_SESSION = "SETTLE_SESSION"
SIDE_EFFECT_RETRY_PREVIOUS = "RETRY_PREVIOUS"


class StateMachine:
    """
    Pure Authoritative State Machine.
    Evaluates events against session snapshots and enforces business invariants.
    """

    def __init__(self, snapshot: Dict[str, Any]):
        # Work on an isolated deep copy to guarantee purity
        self.snapshot = deepcopy(snapshot)

    @staticmethod
    def get_role_assignments(participants: List[Dict[str, Any]], round_index: int) -> Tuple[Optional[str], Optional[str]]:
        """
        Compute Sender and Receiver actor IDs for a given round index (0-indexed).
        Round 0 (Round 1): A is Sender, B is Receiver
        Round 1 (Round 2): B is Sender, A is Receiver
        Round 2 (Round 3): A is Sender, B is Receiver
        """
        p_a = next((p["participant_id"] for p in participants if p.get("label") == "A"), None)
        p_b = next((p["participant_id"] for p in participants if p.get("label") == "B"), None)

        if not p_a or not p_b:
            return None, None

        if round_index % 2 == 0:
            return p_a, p_b
        else:
            return p_b, p_a

    def dispatch(
        self,
        event_type: str,
        actor_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate and transition state based on event_type, actor_id, and payload.
        Returns a standardized transition result dictionary.
        """
        payload = payload or {}
        current_state = self.snapshot.get("status", STATE_LOBBY)
        round_index = self.snapshot.get("current_round_index", 0)
        max_rounds = self.snapshot.get("max_rounds", 3)
        participants = self.snapshot.get("participants", [])
        rounds = self.snapshot.get("rounds", [])
        version = self.snapshot.get("version", 0)
        processed_keys = self.snapshot.get("processed_idempotency_keys", {})

        sender_id, receiver_id = self.get_role_assignments(participants, round_index)

        # ── 1. Check Terminal States ─────────────────────────────────────────
        if current_state in TERMINAL_STATES:
            return self._reject(
                current_state,
                event_type,
                round_index,
                sender_id,
                receiver_id,
                reason=f"Session is in terminal state '{current_state}'. No further actions allowed.",
            )

        # ── 2. Check Idempotency Key ─────────────────────────────────────────
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key:
            if idempotency_key in processed_keys:
                cached = processed_keys[idempotency_key]
                return {
                    "accepted": True,
                    "duplicate": True,
                    "original_transition_id": cached.get("transition_id"),
                    "from_state": current_state,
                    "to_state": current_state,
                    "event_type": event_type,
                    "round_index": round_index,
                    "sender_id": sender_id,
                    "receiver_id": receiver_id,
                    "side_effect": None,
                    "reason": "Duplicate request acknowledged with cached transition.",
                    "next_snapshot": self.snapshot,
                }

        # ── 3. Check Client Version Stale ────────────────────────────────────
        client_version = payload.get("client_version")
        if client_version is not None and client_version < version:
            return self._reject(
                current_state,
                event_type,
                round_index,
                sender_id,
                receiver_id,
                reason=f"Stale client version {client_version}. Current server version is {version}.",
            )

        # ── 4. State Dispatch ────────────────────────────────────────────────

        # ── STATE: LOBBY ─────────────────────────────────────────────────────
        if current_state == STATE_LOBBY:
            if event_type == EVENT_JOIN:
                label = payload.get("label")
                if label not in ("A", "B"):
                    return self._reject(current_state, event_type, round_index, sender_id, receiver_id, "Label must be 'A' or 'B'.")
                # Check duplicate label
                if any(p.get("label") == label for p in participants):
                    return self._reject(current_state, event_type, round_index, sender_id, receiver_id, f"Role {label} is already taken.")
                
                next_snap = deepcopy(self.snapshot)
                new_p = {
                    "participant_id": actor_id or f"p_{label}",
                    "label": label,
                    "ready": payload.get("ready", False),
                    "connected": True,
                }
                next_snap.setdefault("participants", []).append(new_p)

                # Check if both connected
                if len(next_snap["participants"]) == 2 and all(p.get("ready", False) for p in next_snap["participants"]):
                    return self._accept(next_snap, current_state, STATE_READY, event_type, round_index, None, None, None, idempotency_key)
                else:
                    return self._accept(next_snap, current_state, STATE_LOBBY, event_type, round_index, None, None, None, idempotency_key)

            elif event_type == EVENT_READY:
                # Mark actor ready
                next_snap = deepcopy(self.snapshot)
                for p in next_snap.get("participants", []):
                    if p.get("participant_id") == actor_id or p.get("label") == payload.get("label"):
                        p["ready"] = True
                if len(next_snap["participants"]) == 2 and all(p.get("ready", False) for p in next_snap["participants"]):
                    return self._accept(next_snap, current_state, STATE_READY, event_type, round_index, None, None, None, idempotency_key)
                return self._accept(next_snap, current_state, STATE_LOBBY, event_type, round_index, None, None, None, idempotency_key)

            elif event_type == EVENT_ABORT:
                return self._accept(self.snapshot, current_state, STATE_ABORTED, event_type, round_index, sender_id, receiver_id, SIDE_EFFECT_SETTLE_SESSION, idempotency_key)

        # ── STATE: READY ─────────────────────────────────────────────────────
        elif current_state == STATE_READY:
            if event_type == EVENT_START_SESSION:
                # Requires both participants
                if len(participants) < 2:
                    return self._reject(current_state, event_type, round_index, sender_id, receiver_id, "Cannot start session: less than 2 participants.")
                
                s_id, r_id = self.get_role_assignments(participants, 0)
                next_snap = deepcopy(self.snapshot)
                next_snap["current_round_index"] = 0
                # Initialize round 0 container
                round_0 = {
                    "round_id": f"r_{next_snap.get('session_id', 's')}_1",
                    "round_index": 0,
                    "sender_id": s_id,
                    "receiver_id": r_id,
                    "status": "OPEN",
                }
                next_snap.setdefault("rounds", []).append(round_0)
                return self._accept(next_snap, current_state, STATE_INPUT_OPEN, event_type, 0, s_id, r_id, None, idempotency_key)

            elif event_type == EVENT_ABORT:
                return self._accept(self.snapshot, current_state, STATE_ABORTED, event_type, round_index, sender_id, receiver_id, SIDE_EFFECT_SETTLE_SESSION, idempotency_key)

        # ── STATE: INPUT_OPEN ────────────────────────────────────────────────
        elif current_state == STATE_INPUT_OPEN:
            if event_type == EVENT_SUBMIT_INPUT:
                # Actor MUST be current sender
                if actor_id != sender_id:
                    return self._reject(
                        current_state,
                        event_type,
                        round_index,
                        sender_id,
                        receiver_id,
                        f"Unauthorized: Actor '{actor_id}' is not the current sender ('{sender_id}').",
                    )
                # Check round_id validity if provided
                req_round_id = payload.get("round_id")
                curr_round = self._get_current_round(rounds, round_index)
                if req_round_id and curr_round and req_round_id != curr_round.get("round_id"):
                    return self._reject(
                        current_state,
                        event_type,
                        round_index,
                        sender_id,
                        receiver_id,
                        f"Stale round_id '{req_round_id}'. Current round is '{curr_round.get('round_id')}'.",
                    )
                # Max rounds check
                if round_index >= max_rounds:
                    return self._reject(
                        current_state,
                        event_type,
                        round_index,
                        sender_id,
                        receiver_id,
                        f"Max rounds ({max_rounds}) reached. Cannot submit new input.",
                    )

                next_snap = deepcopy(self.snapshot)
                return self._accept(
                    next_snap,
                    current_state,
                    STATE_MODEL_PROCESSING,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    SIDE_EFFECT_RUN_MODEL,
                    idempotency_key,
                )

            elif event_type == EVENT_CHOOSE_END or event_type == EVENT_ABORT:
                return self._accept(self.snapshot, current_state, STATE_SETTLEMENT, event_type, round_index, sender_id, receiver_id, SIDE_EFFECT_SETTLE_SESSION, idempotency_key)

        # ── STATE: MODEL_PROCESSING ──────────────────────────────────────────
        elif current_state == STATE_MODEL_PROCESSING:
            if event_type == EVENT_MODEL_SUCCEEDED:
                next_snap = deepcopy(self.snapshot)
                return self._accept(
                    next_snap,
                    current_state,
                    STATE_SOUND_UPDATE,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    SIDE_EFFECT_UPDATE_ACOUSTIC,
                    idempotency_key,
                )
            elif event_type == EVENT_MODEL_FAILED:
                next_snap = deepcopy(self.snapshot)
                next_snap["last_recoverable_state"] = STATE_MODEL_PROCESSING
                return self._accept(
                    next_snap,
                    current_state,
                    STATE_ERROR,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    None,
                    idempotency_key,
                )

        # ── STATE: SOUND_UPDATE ──────────────────────────────────────────────
        elif current_state == STATE_SOUND_UPDATE:
            if event_type == EVENT_ACOUSTIC_UPDATE_SUCCEEDED:
                next_snap = deepcopy(self.snapshot)
                return self._accept(
                    next_snap,
                    current_state,
                    STATE_RECEIVER_RESPONSE,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    SIDE_EFFECT_NOTIFY_RECEIVER,
                    idempotency_key,
                )
            elif event_type == EVENT_ACOUSTIC_UPDATE_FAILED:
                next_snap = deepcopy(self.snapshot)
                next_snap["last_recoverable_state"] = STATE_SOUND_UPDATE
                return self._accept(
                    next_snap,
                    current_state,
                    STATE_ERROR,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    None,
                    idempotency_key,
                )

        # ── STATE: RECEIVER_RESPONSE ─────────────────────────────────────────
        elif current_state == STATE_RECEIVER_RESPONSE:
            if event_type == EVENT_SUBMIT_RECEIVER_RESPONSE:
                # Actor MUST be current receiver
                if actor_id != receiver_id:
                    return self._reject(
                        current_state,
                        event_type,
                        round_index,
                        sender_id,
                        receiver_id,
                        f"Unauthorized: Actor '{actor_id}' is not the current receiver ('{receiver_id}').",
                    )
                req_round_id = payload.get("round_id")
                curr_round = self._get_current_round(rounds, round_index)
                if req_round_id and curr_round and req_round_id != curr_round.get("round_id"):
                    return self._reject(
                        current_state,
                        event_type,
                        round_index,
                        sender_id,
                        receiver_id,
                        f"Stale round_id '{req_round_id}'. Current round is '{curr_round.get('round_id')}'.",
                    )

                next_snap = deepcopy(self.snapshot)
                # Clear votes for the upcoming round decision
                next_snap["continuation_votes"] = {}

                # If this completed the last round, directly transition to SETTLEMENT!
                if round_index + 1 >= max_rounds:
                    return self._accept(
                        next_snap,
                        current_state,
                        STATE_SETTLEMENT,
                        event_type,
                        round_index,
                        sender_id,
                        receiver_id,
                        SIDE_EFFECT_SETTLE_SESSION,
                        idempotency_key,
                    )

                return self._accept(
                    next_snap,
                    current_state,
                    STATE_ROUND_COMPLETE,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    SIDE_EFFECT_COMPUTE_METRICS,
                    idempotency_key,
                )

            elif event_type == EVENT_TIMEOUT:
                next_snap = deepcopy(self.snapshot)
                next_snap["last_recoverable_state"] = STATE_RECEIVER_RESPONSE
                return self._accept(
                    next_snap,
                    current_state,
                    STATE_ERROR,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    None,
                    idempotency_key,
                )

            elif event_type == EVENT_CHOOSE_END or event_type == EVENT_ABORT:
                return self._accept(self.snapshot, current_state, STATE_SETTLEMENT, event_type, round_index, sender_id, receiver_id, SIDE_EFFECT_SETTLE_SESSION, idempotency_key)

        # ── STATE: ROUND_COMPLETE ────────────────────────────────────────────
        elif current_state == STATE_ROUND_COMPLETE:
            # Either actor can choose end
            if event_type == EVENT_CHOOSE_END:
                next_snap = deepcopy(self.snapshot)
                return self._accept(
                    next_snap,
                    current_state,
                    STATE_SETTLEMENT,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    SIDE_EFFECT_SETTLE_SESSION,
                    idempotency_key,
                )

            elif event_type == EVENT_CHOOSE_CONTINUE:
                if not actor_id or actor_id not in (sender_id, receiver_id):
                    return self._reject(current_state, event_type, round_index, sender_id, receiver_id, "Unknown participant.")
                
                next_snap = deepcopy(self.snapshot)
                votes = next_snap.setdefault("continuation_votes", {})
                votes[actor_id] = "continue"

                # Check if both have agreed
                if len(votes) >= 2 and all(v == "continue" for v in votes.values()):
                    # Both agreed -> Advance round!
                    new_round_index = round_index + 1
                    new_s_id, new_r_id = self.get_role_assignments(participants, new_round_index)
                    next_snap["current_round_index"] = new_round_index
                    next_snap["continuation_votes"] = {}
                    # Append new round container
                    new_round = {
                        "round_id": f"r_{next_snap.get('session_id', 's')}_{new_round_index + 1}",
                        "round_index": new_round_index,
                        "sender_id": new_s_id,
                        "receiver_id": new_r_id,
                        "status": "OPEN",
                    }
                    next_snap.setdefault("rounds", []).append(new_round)
                    return self._accept(
                        next_snap,
                        current_state,
                        STATE_INPUT_OPEN,
                        event_type,
                        new_round_index,
                        new_s_id,
                        new_r_id,
                        SIDE_EFFECT_START_NEXT_ROUND,
                        idempotency_key,
                    )
                else:
                    # One participant agreed -> Waiting for partner
                    return self._accept(
                        next_snap,
                        current_state,
                        STATE_NEXT_ROUND_PENDING,
                        event_type,
                        round_index,
                        sender_id,
                        receiver_id,
                        None,
                        idempotency_key,
                    )

            elif event_type == EVENT_ABORT:
                return self._accept(self.snapshot, current_state, STATE_ABORTED, event_type, round_index, sender_id, receiver_id, SIDE_EFFECT_SETTLE_SESSION, idempotency_key)

        # ── STATE: NEXT_ROUND_PENDING ────────────────────────────────────────
        elif current_state == STATE_NEXT_ROUND_PENDING:
            if event_type == EVENT_CHOOSE_CONTINUE:
                if not actor_id or actor_id not in (sender_id, receiver_id):
                    return self._reject(current_state, event_type, round_index, sender_id, receiver_id, "Unknown participant.")
                
                next_snap = deepcopy(self.snapshot)
                votes = next_snap.setdefault("continuation_votes", {})
                votes[actor_id] = "continue"

                if len(votes) >= 2 and all(v == "continue" for v in votes.values()):
                    new_round_index = round_index + 1
                    new_s_id, new_r_id = self.get_role_assignments(participants, new_round_index)
                    next_snap["current_round_index"] = new_round_index
                    next_snap["continuation_votes"] = {}
                    new_round = {
                        "round_id": f"r_{next_snap.get('session_id', 's')}_{new_round_index + 1}",
                        "round_index": new_round_index,
                        "sender_id": new_s_id,
                        "receiver_id": new_r_id,
                        "status": "OPEN",
                    }
                    next_snap.setdefault("rounds", []).append(new_round)
                    return self._accept(
                        next_snap,
                        current_state,
                        STATE_INPUT_OPEN,
                        event_type,
                        new_round_index,
                        new_s_id,
                        new_r_id,
                        SIDE_EFFECT_START_NEXT_ROUND,
                        idempotency_key,
                    )
                else:
                    return self._accept(
                        next_snap,
                        current_state,
                        STATE_NEXT_ROUND_PENDING,
                        event_type,
                        round_index,
                        sender_id,
                        receiver_id,
                        None,
                        idempotency_key,
                    )

            elif event_type in (EVENT_CHOOSE_END, EVENT_TIMEOUT):
                next_snap = deepcopy(self.snapshot)
                return self._accept(
                    next_snap,
                    current_state,
                    STATE_SETTLEMENT,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    SIDE_EFFECT_SETTLE_SESSION,
                    idempotency_key,
                )

            elif event_type == EVENT_ABORT:
                return self._accept(self.snapshot, current_state, STATE_ABORTED, event_type, round_index, sender_id, receiver_id, SIDE_EFFECT_SETTLE_SESSION, idempotency_key)

        # ── STATE: ERROR ─────────────────────────────────────────────────────
        elif current_state == STATE_ERROR:
            if event_type == EVENT_RECOVER:
                target_state = self.snapshot.get("last_recoverable_state", STATE_INPUT_OPEN)
                next_snap = deepcopy(self.snapshot)
                return self._accept(
                    next_snap,
                    current_state,
                    target_state,
                    event_type,
                    round_index,
                    sender_id,
                    receiver_id,
                    SIDE_EFFECT_RETRY_PREVIOUS,
                    idempotency_key,
                )
            elif event_type == EVENT_ABORT:
                return self._accept(self.snapshot, current_state, STATE_ABORTED, event_type, round_index, sender_id, receiver_id, SIDE_EFFECT_SETTLE_SESSION, idempotency_key)

        # ── Illegal Event / Transition Fallthrough ───────────────────────────
        return self._reject(
            current_state,
            event_type,
            round_index,
            sender_id,
            receiver_id,
            f"Illegal transition: Event '{event_type}' is not permitted in state '{current_state}'.",
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _accept(
        self,
        next_snap: Dict[str, Any],
        from_state: str,
        to_state: str,
        event_type: str,
        round_index: int,
        sender_id: Optional[str],
        receiver_id: Optional[str],
        side_effect: Optional[str],
        idempotency_key: Optional[str],
    ) -> Dict[str, Any]:
        transition_id = f"t_{next_snap.get('version', 0) + 1}_{event_type}"
        next_snap["status"] = to_state
        next_snap["version"] = next_snap.get("version", 0) + 1

        if idempotency_key:
            next_snap.setdefault("processed_idempotency_keys", {})[idempotency_key] = {
                "transition_id": transition_id,
                "event_type": event_type,
                "to_state": to_state,
            }

        return {
            "accepted": True,
            "duplicate": False,
            "transition_id": transition_id,
            "from_state": from_state,
            "to_state": to_state,
            "event_type": event_type,
            "round_index": round_index,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "side_effect": side_effect,
            "reason": None,
            "next_snapshot": next_snap,
        }

    def _reject(
        self,
        current_state: str,
        event_type: str,
        round_index: int,
        sender_id: Optional[str],
        receiver_id: Optional[str],
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "accepted": False,
            "duplicate": False,
            "transition_id": None,
            "from_state": current_state,
            "to_state": current_state,
            "event_type": event_type,
            "round_index": round_index,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "side_effect": None,
            "reason": reason,
            "next_snapshot": self.snapshot,
        }

    @staticmethod
    def _get_current_round(rounds: List[Dict[str, Any]], round_index: int) -> Optional[Dict[str, Any]]:
        for r in rounds:
            if r.get("round_index") == round_index:
                return r
        return None
