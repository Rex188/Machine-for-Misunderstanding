# Blind Test Implementation Log

Project: A Machine for Misunderstanding  
Path: `project2/blind_test/`  
Last updated: 2026-10-02

## Project direction

The system treats communication as a sequence of interpretations rather than direct text transmission.

Core decisions:

- The server is authoritative for session state.
- A marker is the authoritative temporal reference for acoustic change.
- VCV Rack continuously produces sound; there is no fixed 15-second playback window.
- Receiver privacy is preserved until settlement.
- Screen recording is an optional external artifact. Audio recording is not required.

## Phase 1 — Canonical SQLite Data Layer

Status: **Completed and tested**  
Commit: `d321c83 feat(blind_test): complete Phase 1 canonical SQLite data layer with tests`

Implemented files: `schema.sql`, `db.py`, and `test_db.py`.

The database contains 10 entities: `sessions`, `participants`, `rounds`, `input_events`, `model_runs`, `markers`, `receiver_responses`, `metrics`, `state_events`, and `artifacts`.

Verified properties:

- SQLite foreign keys enabled;
- WAL journal mode enabled;
- 5-second busy timeout;
- thread-local database connections;
- no cross-thread connection sharing;
- foreign-key constraints and performance indexes;
- unique `client_submission_id` replay protection;
- full canonical session export across all 10 entities.

The data layer supports atomic commits for sender input/marker creation and receiver response/metrics completion. External model and OSC calls remain outside SQLite transactions.

## Phase 2 — Authoritative State Machine

Status: **Completed and tested**  
Commit: `348a8b0 feat(blind_test): complete Phase 2 pure authoritative state machine with exhaustive tests`

Implemented files: `state_machine.py` and `test_state_machine.py`. Continuation vote persistence was added to `schema.sql` and `db.py`.

Implemented states: `LOBBY`, `READY`, `INPUT_OPEN`, `MODEL_PROCESSING`, `SOUND_UPDATE`, `RECEIVER_RESPONSE`, `ROUND_COMPLETE`, `NEXT_ROUND_PENDING`, `SETTLEMENT`, `ERROR`, and `ABORTED`.

Verified properties:

- pure state machine with no database, HTTP, LLM, OSC, VCV, or frontend dependencies;
- explicit event dispatch and side-effect instructions;
- automatic role alternation across rounds;
- maximum of three rounds;
- strict sender and receiver authorization;
- stale `round_id` and `client_version` rejection;
- idempotent repeated submissions;
- terminal locking of `SETTLEMENT` and `ABORTED`;
- recoverable model and acoustic error states.

## Phase 3 — Application Orchestrator and Deterministic Metrics

Status: **Completed and tested**  
Commit: **Not committed; changes intentionally remain uncommitted**

Implemented files: `metrics.py`, `acoustic_bridge.py`, `service.py`, `test_metrics.py`, `test_acoustic_bridge.py`, and `test_service.py`.

The metrics engine is pure, validates finite VADC values in `[0, 1]`, supports zero vectors, preserves raw distances, preserves confidence-adjusted distances separately, and returns `null` inter-round drift for the first round.

The normalized Euclidean distance uses `sqrt(3)` as the maximum distance of the unit VAD cube.

The acoustic bridge defines `ModelBackend`, `OscTransport`, `FakeModelBackend`, and `FakeOscTransport`. The frozen OSC mapping contains eight channels: timbre, frequency, amplitude, envelope, mode, chord, type, and noise.

The application service coordinates the database, state machine, metrics, model backend, OSC transport, and privacy projections.

Verified behavior:

- complete three-round flow;
- exactly one committed marker per successful input;
- failed model calls create no marker;
- failed OSC calls create no marker;
- duplicate idempotency keys return the original result;
- Receiver projection does not expose Sender text, Sender VAD, model VAD, or model reasoning before settlement.

## Phase 4 — HTTP API Integration

Status: **Completed and tested**  
Commit: **Not committed; changes intentionally remain uncommitted**

Implemented files: `server.py` and `test_server.py`.

The HTTP gateway uses standard-library `ThreadingHTTPServer`, thread-local database connections, token authentication through `X-Session-Token`, unified JSON errors, traceback suppression, participant-specific projections, and version-based long polling.

Implemented endpoints: `/api/blind/health`, `/join`, `/ready`, `/start`, `/state`, `/submit_input`, `/submit_receiver`, `/continue`, `/end`, and `/summary`.

Verified behavior:

- two-client join flow;
- third participant rejection;
- authentication and invalid-token rejection;
- sender/receiver role enforcement;
- stale-version rejection;
- duplicate request idempotency;
- concurrent input submission with one and only one marker;
- long-poll timeout and wake-up;
- malformed JSON handling;
- no traceback leakage;
- privacy projection enforcement.

## Phase 5A — Real UDP/OSC Transport

Status: **Completed and tested**  
Commit: **Not committed; changes intentionally remain uncommitted**

Implemented files: `real_osc.py` and `test_real_osc.py`.

Implemented standard-library OSC 1.0 encoding, four-byte padding, big-endian 32-bit floats, configurable host/port/timeout, strict validation of all eight voltage channels, explicit network failure status, and compatibility with the existing `OscTransport` interface.

Tests cover packet encoding, voltage boundaries, invalid values, local UDP loopback, exact eight-packet dispatch, and service integration.

## Phase 5B — Real Local Model Backend

Status: **Completed and tested**  
Commit: **Not committed; changes intentionally remain uncommitted**

Implemented files: `real_model.py` and `test_real_model.py`.

Implemented local Qwen2.5-1.5B support, optional LoRA loading from `models/qwen_lora/`, MPS/CUDA/CPU selection, no external network request, no hardcoded credentials, prompt version tracking, raw output preservation, and latency tracking.

Invalid JSON, missing dimensions, out-of-range values, NaN, and Infinity are rejected. Invalid model output is never silently converted into a neutral vector, and model failure creates no committed marker.

Tests cover clean JSON, Markdown-wrapped JSON, surrounding explanation, valid output, invalid ranges, missing fields, non-JSON output, service integration, and privacy projection.

## Regression status

The reported Phases 1–5B suite passes: `test_db.py`, `test_state_machine.py`, `test_metrics.py`, `test_acoustic_bridge.py`, `test_service.py`, `test_server.py`, `test_real_osc.py`, and `test_real_model.py`.

The automated system is ready for physical VCV rehearsal. Final real-browser and real-patch acceptance has not yet been completed.

## Current architecture

Browser or HTTP client → `server.py` → `service.py` → state machine, database, real/fake model backend, acoustic bridge, and real/fake OSC transport → VCV Rack.

## Pending work

### Phase 5C — Real VCV and live rehearsal

- verify the actual VCV patch responds to all eight OSC addresses;
- verify neutral and extreme VAD states physically;
- verify continuous sound across multiple markers;
- verify safe audio levels and no clipping;
- verify marker timestamps against screen recording;
- run a complete two-browser session;
- verify settlement and VCV safe idle behavior.

### Phase 6 — Frontend

Pending frontend files: `web/index.html`, `web/style.css`, `web/app.js`, `web/coords.js`, and `web/revelation.js`.

The frontend must consume existing HTTP projections and must not redefine state-machine behavior.

## Decisions still to freeze

1. Confirm that `inter_round_drift` remains normalized Euclidean distance rather than the original cosine distance.
2. Confirm strict-versus-clamping behavior for direct metric and voltage helper calls.
3. Protect `/api/blind/summary` with a session token or an explicit one-time reveal token.
4. Confirm the physical VCV patch mapping for all eight OSC addresses.
5. Confirm whether settlement stops VCV or returns it to a safe idle state.
6. Define the exact visible marker format used in the external screen recording.

## Development policy

- Keep fake backends for deterministic automated tests.
- Keep real model and real OSC adapters behind existing interfaces.
- Do not place model or network calls inside SQLite transactions.
- Do not modify the VCV patch automatically.
- Do not commit changes without explicit authorization.
- Preserve all previous regression tests after every phase.
