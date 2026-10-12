# A Machine for Misunderstanding: Blind Test Web Experiment System
## Implementation Plan & System Specification

> **Project**: Portfolio Project 2 — *A Machine for Misunderstanding*  
> **Status**: Specification Frozen / Ready for Implementation  
> **Environment**: Local Area Network (LAN) / Localhost  
> **Language**: All UI / Front-end copy in **English**  
> **Audio Engine**: Single local VCV Rack instance listening on UDP port 7001 (cvOSCcv)  
> **Primary File**: `portfolio/project2/BLIND_TEST_PLAN.md`

---

## 1. Executive Summary & Conceptual Grounding

### 1.1 The Core Thesis
> *"Communication is not transmission. It is interpretation."*  
> *"We build systems to control uncertainty, yet those systems inevitably create new forms of uncertainty."*

Modern communication systems obsess over high fidelity, zero latency, and deterministic compression. This experiment system inverts that premise: it subjects human phenomenological, somatic language to an algorithmic black-box (LLM) and a modular synthesizer (VCV Rack). 

The goal of the **Blind Test Web System** is to empirically observe, mathematically quantify, and poetically visualize the **"Communication Gap" (Misunderstanding)** as two human participants converse solely through the acoustic mediation of generative synthesis.

---

## 2. Mathematical Formulation & Conceptual Disambiguation

### 2.1 The Conceptual Problem with Naive Metrics & Confidence
In prior iterations, two major flaws threatened experimental validity:
1. **Misattributing the Model Gap**: Comparing sender self-reported VAD with the model's inferred VAD was mislabeled as "model translation error". In reality, the model only reads the somatic text—it never reads the sender's VAD. Therefore, this gap actually measures the **Semantic / Linguistic Externalization Gap** (the disparity between what a human internally feels and how an LLM interprets their verbalized prose).
2. **Confidence Conflation & False Damping**: Confidence encompasses three fundamentally heterogeneous psychological/computational constructs:
   - **$C_{\text{sender}}$ (Self-State Certainty)**: How clearly the sender recognizes their own bodily condition.
   - **$C_{\text{model}}$ (Inference Confidence)**: The LLM's internal certainty in decoding semantic nuances.
   - **$C_{\text{receiver}}$ (Perceptual Certainty)**: How distinct or ambiguous the receiver finds their auditory impression.
   Putting these three into a single damping formula ($\kappa$) artificially compresses large distances into "small misunderstandings" whenever someone is uncertain. **A high distance accompanied by low confidence is genuine acoustic ambiguity—it must never be mathematically disguised as low misunderstanding.**

### 2.2 Clean Decoupling: Raw Affective Distances & Independent Confidences

All spatial metrics are computed strictly in normalized 3D Euclidean affective space, **unaltered and uncompressed**:

$$\vec{x}_{\text{sender}} = \begin{bmatrix} V_{\text{sender}} \\ A_{\text{sender}} \\ D_{\text{sender}} \end{bmatrix}, \quad
\vec{x}_{\text{model}} = \begin{bmatrix} V_{\text{model}} \\ A_{\text{model}} \\ D_{\text{model}} \end{bmatrix}, \quad
\vec{x}_{\text{receiver}} = \begin{bmatrix} V_{\text{receiver}} \\ A_{\text{receiver}} \\ D_{\text{receiver}} \end{bmatrix} \in [0, 1]^3$$

Normalized Euclidean distance function ($d \in [0, 1]$):
$$d(\vec{x}_a, \vec{x}_b) = \frac{\|\vec{x}_a - \vec{x}_b\|_2}{\sqrt{3}}$$

#### The Three Core Spatial Metrics:
1. **`raw_distance_semantic` ($D_{\text{sem}}$) — Text Externalization vs. Model Interpretation**:
   $$D_{\text{sem}} = d(\vec{x}_{\text{sender}}, \vec{x}_{\text{model}})$$
   *Measures the discrepancy between internal somatic self-report and textual representation as decoded by the model.*
2. **`raw_distance_acoustic` ($D_{\text{acoust}}$) — Synthesizer Target vs. Perceived Impression**:
   $$D_{\text{acoust}} = d(\vec{x}_{\text{model}}, \vec{x}_{\text{receiver}})$$
   *Measures the physical impedance, patch modulation drift (Coordinator), and human psychoacoustic decoding variance.*
3. **`raw_distance_interpersonal` ($D_{\text{total}}$) — Total Interpersonal Misunderstanding**:
   $$D_{\text{total}} = d(\vec{x}_{\text{sender}}, \vec{x}_{\text{receiver}})$$
   *The primary experimental metric: the unweighted geometric divergence between Sender's original feeling and Receiver's perceived state.*

4. **Inter-Round Dynamics (Normalized Euclidean, Zero Singularity)**:
   *Cosine distance has severe mathematical flaws in $[0, 1]^3$: if a vector approaches the origin $[0, 0, 0]$ (a valid physiological state: extreme paralysis/hypothermia), division-by-zero occurs. Furthermore, $[0, 0, 0]$ is not neutral baseline. Therefore, we use strictly bounded Normalized Euclidean Distances:*
   
   - **`somatic_shift_distance` ($D_{\text{shift}}^{(r)}$) — Perceptual vs. Post-Shift State**:
     $$D_{\text{shift}}^{(r)} = d\left(\vec{x}_{\text{receiver}}^{(r)}, \vec{x}_{\text{sender}}^{(r+1)}\right) = \frac{\left\|\vec{x}_{\text{sender}}^{(r+1)} - \vec{x}_{\text{receiver}}^{(r)}\right\|_2}{\sqrt{3}} \in [0, 1]$$
     *Measures how far the participant's internal state shifted from what they heard in Round $r$ to what they formulated as Sender in Round $r+1$.*
   
   - **`intent_drift_distance` ($D_{\text{drift}}^{(r \to r+1)}$) — Dialogue Thematic Drift**:
     $$D_{\text{drift}}^{(r \to r+1)} = d\left(\vec{x}_{\text{sender}}^{(r)}, \vec{x}_{\text{sender}}^{(r+1)}\right) = \frac{\left\|\vec{x}_{\text{sender}}^{(r+1)} - \vec{x}_{\text{sender}}^{(r)}\right\|_2}{\sqrt{3}} \in [0, 1]$$
     *Measures how far the dialogue's creative intent drifted in 3D affective space between successive transmissions.*

#### Independent Metacognitive Reporting (Logged & Reported Separately):
Every entry in data logs and final reports outputs the raw distance alongside the three distinct confidences:
- `raw_distance` ($D_{\text{total}}$)
- `sender_confidence` ($C_{\text{sender}} \in [0, 1]$)
- `model_confidence` ($C_{\text{model}} \in [0, 1]$)
- `receiver_confidence` ($C_{\text{receiver}} \in [0, 1]$)

**Classification Matrix (For Revelation Analysis)**:
- **High Distance + High Confidences**: *Confirmed Misunderstanding* (Both parties are certain, but fundamentally opposed).
- **High Distance + Low Receiver Confidence**: *Perceptual Ambiguity / Atmospheric Drift* (The musical medium dissolved definitive communication into abstraction).
- **Low Distance + High Confidences**: *Acoustic Resonance / Genuine Alignment*.

---

## 3. Strict Experimental Protocol & Physical Setup

### 3.1 Strict Double-Blind Information Masking
During the active session, strict data isolation is enforced by the software:
* **The Receiver CANNOT see**:
  - The Sender's written text;
  - The Sender's self-assessed VAD;
  - The Model's inferred VAD or reasoning.
* **The Sender CANNOT see**:
  - The Model's inferred VAD;
  - The Receiver's ratings, notes, or somatic shift evaluation.
* **Both parties see ONLY**:
  - Their own active input forms (when it is their turn);
  - A clean turn status message (e.g., *"Partner is encoding state..."*, *"Soundscape is playing..."*);
  - Their own historical inputs.
* Only after the session is explicitly terminated via **"End Dialogue"** are all masked data simultaneously revealed in the **Revelation Dashboard**.

### 3.2 Physical Space & Acoustic Constraints
* **Physical Isolation**: Both participants sit in the same physical room or listening area, but positioned back-to-back or separated by a partition. **They cannot see each other's screens, and verbal/gestural communication is strictly prohibited.**
* **Simultaneous Audio Environment**: Both participants hear the sound at the exact same time through the same room studio monitors (or synchronized headphones).
* **Continuous Sound Generation (No Silent Gaps)**:
  - The VCV Rack sound does **NOT** stop after 15–20 seconds.
  - Instead, the sound **plays continuously as an ongoing, sustaining generative soundscape (ambient drone / generative cadence)**.
  - When a participant submits a new input, the Python bridge smoothly transitions (glides) the VCV Rack parameters to the new affective state.
  - The sound continues to play in the room while the Receiver listens and reflects, and keeps playing until the next input triggers a subsequent parameter transition!

---

## 3. Experimental Workflow & Protocol

### 3.1 Topology & Role Progression

```text
[Participant A: Sender]                          [Participant B: Receiver]
          │                                                │
1. Enter Somatic Text + Self VADC                          │
          │                                                │
          ▼                                                │
   [Local Python Server (ThreadingHTTPServer)]             │
   • Model Inference (Qwen LoRA / DeepSeek)                │
   • Compute 8-Ch Clean Voltage Vectors                    │
   • Dispatch OSC to UDP 7001 (cvOSCcv)                    │
          │                                                │
          ▼                                                │
  [Single VCV Rack Instance]                               │
  • Continuous Generative Soundscape                       │
  • Sound drones / plays endlessly until next input        │
          │                                                │
          │ ─── Continuous Acoustic Audio in Room ────────► │
          │                                                │
          │                               2. Listen to continuous audio
          │                               3. Submit perceived VADC
          │                               4. Describe Somatic Shift
          │                                                │
          ▼                                                ▼
  [Round Complete: Option to Continue to Round 2 OR End Dialogue]
          │                                                │
  [Roles SWAP for Round 2] ◄───────────────────────────────┘
  (B becomes Sender using felt somatic shift as basis;
   A becomes Receiver)
          │
          ▼
  [Settlement Triggered by Either Client]
          │
          ▼
  [Both Clients Automatically Transition to Revelation Dashboard]
```

### 3.2 Turn-Taking Lifecycle (Strict Definition of "Round")

* **Definition of a Round**: **1 Round = 1 Sound Transmission & 1 Evaluation Cycle**.
* **Total Experiment Scope**: **Strictly 3 Rounds Maximum (3 Sound Transmissions, 2 Role Swaps)**:
  - **Round 1**: Participant A is **Sender**; Participant B is **Receiver**.
    - A submits prose + self VAD $\to$ Model generates VCV continuous soundscape.
    - B listens to continuous sound in room $\to$ B submits perceived VAD + somatic shift text.
  - **Round 2 (Role Swap 1)**: Participant B becomes **Sender**; Participant A becomes **Receiver**.
    - B formulates input using their somatic reaction to the previous sound $\to$ Model updates VCV soundscape.
    - A listens to continuous sound in room $\to$ A submits perceived VAD + somatic shift text.
  - **Round 3 (Role Swap 2)**: Participant A becomes **Sender**; Participant B becomes **Receiver**.
    - A formulates input based on their felt shift $\to$ Model updates VCV soundscape.
    - B listens $\to$ B submits perceived VAD + somatic shift text.
  - **Automatic Completion**: The session immediately concludes after Round 3 finishes.
* **Early Termination Rule**:
  - At the completion of **Round 1** or **Round 2**, either participant can click **"End Dialogue & Reveal"**.
  - Both screens immediately transition synchronously to the **Revelation Dashboard**.

---

## 4. Front-End & UI/UX Design Specification (All English)

### 4.1 Aesthetic Direction
* **Theme**: Deep Kurogane / Obsidian Dark (`--bg-main: #0c0f14`, `--bg-card: #151a22`, `--border: #273142`) matching the existing Project 2 aesthetics.
* **Typography**: Monospace (`JetBrains Mono`) for metrics and states; Serif (`Noto Serif` / `Georgia`) for somatic literary prompts and quotes.
* **Non-Ugly Coordinate Board**:
  - **2D Affective Plane Canvas**:
    - X-Axis: **Valence** (*Left: Oppressive / Frozen / Dark* $\longleftrightarrow$ *Right: Expansive / Luminous / Warm*)
    - Y-Axis: **Arousal** (*Bottom: Lethargic / Suspended / Low-Energy* $\longleftrightarrow$ *Top: Agitated / Spasmic / High-Energy*)
    - Interactive cursor: Glowing radiant focal point with trailing halo, snapping coordinate readout.
  - **1D Dominance Siphon**:
    - Linear gradient slider with semantic markers: *Swallowed / Powerless* $\longleftrightarrow$ *Grounded* $\longleftrightarrow$ *Assertive / Sovereign*.
  - **Confidence Selector**:
    - Segmented capsule: `0.2 (Diffused/Ambiguous)` | `0.5 (Moderate)` | `0.8 (Distinct)` | `1.0 (Absolute)`.

### 4.2 Screens & States

1. **Lobby / Waiting Screen**:
   - Connection indicator (Local LAN Host status, VCV OSC status).
   - Role badge (`PARTICIPANT A [SENDER]` / `PARTICIPANT B [RECEIVER]`).
   - Instructions and briefing in English.

2. **Input / Synthesis Active Screen**:
   - Somatic prose text area with word counter.
   - Interactive VADC Coordinate Board.
   - Transmission status banner.

3. **Live Listening & Receiving Screen**:
   - Audio waveform pulse visualizer indicating active soundscape.
   - Receiver VADC grading board.
   - Somatic shift feedback card.

4. **The Revelation & Settlement Dashboard**:
   - Triggered when either party ends the dialogue.
   - **Dialogue Chronicle**: Full side-by-side transcript of inputs, perceived feelings, and responses.
   - **3D Affective Drift Trajectory**: Three.js / Canvas visualization displaying how the conversation drifted through the VAD cube across rounds.
   - **Quantified Metric Cards**:
     - *Total Misunderstanding ($D_{\text{total}}$)*
     - *Semantic Externalization Gap ($D_{\text{sem}}$)*
     - *Acoustic Perceptual Drift ($D_{\text{acoust}}$)*
     - *Somatic Shift Distance ($D_{\text{shift}}$)*
     - *Intent Thematic Drift ($D_{\text{drift}}$)*
   - **Export Button**: Single click to download `session_<timestamp>.json` and `session_<timestamp>.csv`.

---

## 5. System Architecture & Isolated Workspace

To protect the existing `workflow/` codebase and maintain zero clutter, all blind test code will reside in a dedicated, isolated workspace:

```text
portfolio/project2/blind_test/
├── server.py              # Dedicated standalone LAN HTTP server (port 7071)
├── manager.py             # Session state machine, turn-locking & unconfounded metrics
├── blind_test_log.jsonl   # Local persistent experiment logs
├── start.sh               # Dedicated 1-click startup script for blind test
└── web/
    ├── index.html         # All-English dedicated blind test interface
    ├── style.css          # Dedicated dark obsidian styling
    ├── main.js            # Dual-client sync & state machine
    └── coords.js          # High-aesthetic 2D/3D affective board
```

*Note: The blind test backend will cleanly import only the sound calculation and OSC bridge from `../workflow/llm_sound_interactive.py` (`compute_sound_elements`, `osc_msg`) without modifying any existing workflow files.*

### 5.1 Frozen 8-Channel OSC Routing Contract
The acoustic bridge sends **exactly 8 distinct physical voltage channels**. All duplicate address aliases (including `/param/scale`) are completely removed:

```python
OSC_CHANNELS = {
    "/param/timbre": "timbre_v",        # Plaits Timbre / Cutoff
    "/param/frequency": "frequency_v",  # V/Oct Pitch offset
    "/param/amplitude": "amplitude_v",  # VCA master level
    "/param/envelope": "envelope_v",    # Decay / Attack shape
    "/param/mode": "mode_v",            # Modal scale degree (sole authority)
    "/param/chord": "chord_v",          # Chord root degree offset
    "/param/type": "type_v",            # Chord triad/7th/9th voicing
    "/param/noise": "noise_v",          # Plateau reverb decay & caustics
}
```

*Continuous Sound Rule*: The Python bridge streams these 8 voltages to UDP port 7001 using glide interpolation. Sound runs continuously without artificial pauses, countdowns, or stop triggers.

### 5.2 Canonical 10-Table SQLite Relational Architecture
The database layer implements **exactly 10 independent tables** (strictly keeping `input_events` independent to ensure idempotency and auditability):
1. `sessions`
2. `participants`
3. `rounds`
4. `input_events` (Independent audit of all sender submissions)
5. `model_runs`
6. `markers` (Immutable authoritative acoustic events)
7. `receiver_responses`
8. `metrics`
9. `state_events` (Append-only state audit log)
10. `artifacts` (External audiovisual recording references)

### 5.3 Concurrency, Session Locking & Double-Blind Data Sanitization
To solve the single-threaded `HTTPServer` and global `CURRENT_STATE` limitations:
* **Threaded HTTP Backend**: `server.py` inherits from `http.server.ThreadingHTTPServer` to handle concurrent polling and submissions from both clients simultaneously.
* **Thread-Safe Session Manager**: A dedicated `BlindSessionManager` with `threading.Lock` coordinates turn transitions, state changes, and timeouts atomically.
* **Role-Sanitized Polling (`GET /api/blind/poll?role=A`)**:
  - The server explicitly filters the state response according to the requesting client's role.
  - While a round is active, the Receiver's payload **omits** `sender_text`, `sender_vad`, and `model_vad`.
  - The Sender's payload **omits** `model_vad`, `receiver_vad`, and `receiver_somatic_shift`.
  - Only when `session.status == "revealed"` does the server deliver the full unmasked session dictionary to both endpoints.

### 5.4 Prerequisite Security Neutralization (Completed)
* Hardcoded API keys in `workflow/llm_sound_interactive.py` and `workflow/llm_to_vad.py` have been neutralized and wiped.
* The system now strictly loads credentials from `os.environ["DEEPSEEK_API_KEY"]` or defaults to the local offline Qwen model (`USE_LOCAL_MODEL=1`).

---

## 6. Data Persistence Contract (`blind_test_log.jsonl`)

Every completed turn records an unconfounded, audit-ready schema:
```json
{
  "session_id": "session_20261001_143000",
  "round": 1,
  "turn": 1,
  "sender_role": "A",
  "receiver_role": "B",
  "sender_text": "The key hesitated in the lock. My tongue seized up...",
  "sender_vad": {"valence": 0.15, "arousal": 0.85, "dominance": 0.10},
  "sender_confidence": 0.90,
  "model_vad": {"valence": 0.22, "arousal": 0.78, "dominance": 0.20},
  "model_confidence": 0.82,
  "model_reasoning": "Somatic paralysis paired with acute internal conflagration...",
  "receiver_vad": {"valence": 0.65, "arousal": 0.35, "dominance": 0.50},
  "receiver_confidence": 0.45,
  "receiver_somatic_shift": "Felt a cooling sensation in the chest, breathing slowed down...",
  "voltages": {
    "timbre_v": 2.1,
    "frequency_v": -1.2,
    "amplitude_v": 4.5,
    "envelope_v": 1.8,
    "mode_v": -4.0,
    "chord_v": 1.0,
    "type_v": 0.0,
    "noise_v": 2.5
  },
  "metrics": {
    "raw_distance_interpersonal": 0.493,
    "raw_distance_semantic": 0.082,
    "raw_distance_acoustic": 0.441,
    "sender_confidence": 0.90,
    "model_confidence": 0.82,
    "receiver_confidence": 0.45,
    "classification": "Perceptual Ambiguity with High Divergence"
  },
  "timestamp": "2026-10-01T14:30:15"
}
```

---

## 7. Strict Engineering Red Lines & Anti-Pattern Prohibitions

To ensure the integrity of the scientific experiment and system architecture, the following 9 anti-patterns are strictly prohibited:

1. **NO Fake Countdown Audio Timers**: Never use front-end timers or artificial countdown clocks pretending to be "audio completion events". The VCV Rack soundscape is continuously running; Receiver reflects and submits at their own natural pace.
2. **NO Naive Polling Masquerading as a State Machine**: The server must maintain a real, robust, state-machine backend (`IDLE` $\to$ `WAITING_SENDER_INPUT` $\to$ `SYNTHESIZING` $\to$ `WAITING_RECEIVER_EVAL` $\to$ `ROUND_COMPLETE` $\to$ `REVEALED`) where all state transitions are atomic, validated, and role-enforced.
3. **NO Role Collisions / Duplicate Role Submissions**: Enforce strict client pairing and session role locking (e.g. unique `client_token` bound to Role A and Role B upon session join). Prevent two browser tabs from submitting under the same active role simultaneously; unauthorized or duplicate attempts must be rejected with HTTP 403/409.
4. **NO Global Variable Overwrites Across Rounds**: Never overwrite state in a naive mutable dictionary. Maintain an append-only, immutable history array of completed rounds per session (`session.history = []`).
5. **NO Silent Fallback on LLM Failure**: If the LLM throws an exception, times out, or returns malformed JSON, **NEVER** silently inject a dummy `[0.5, 0.5, 0.5]` without flagging. Any fallback must be explicitly marked in the log and state (`"model_status": "error"`, `"is_fallback": true`, `"error_trace": "..."`), and the UI must display a clear failure warning rather than faking an interpretation.
6. **NO curl-Only Mock Verification**: The system verification MUST involve opening two actual physical browser windows/devices simultaneously, verifying real-time synchronization, and checking actual acoustic audio modulation output from VCV Rack.
7. **NO Unauthorized Sound Mapping Alterations**: Do NOT arbitrarily invent or alter established VCV voltage mappings or equations defined in `MVP.md` and `声音映射与媒介协调器执行方案.md`. Strictly reuse `compute_sound_elements()` and `osc_msg()` as the authoritative bridge.
8. **ZERO External Dependencies / Cloud Bloat**: Absolutely NO external pip libraries, cloud databases, or third-party web frameworks added just to "make it run". Strictly use Python standard library (`http.server.ThreadingHTTPServer`, `socket`, `json`, `urllib`, `threading`, `uuid`) and standard HTML5/CSS/Vanilla JS.
9. **NO Vanity Dashboards with Untraceable Data**: Every point, distance, and curve rendered on the final Revelation Dashboard must trace back directly to raw, immutable session records (`session_id`, exact timestamps, raw text, and uncompressed float vectors).

---

## 8. Verification & Audit Checklist

1. **Math Integrity**:
   - Confirm $D_{\text{total}}, D_{\text{sem}}, D_{\text{acoust}}, D_{\text{shift}}, D_{\text{drift}} \in [0, 1]$ across all boundary cases.
   - Verify no division-by-zero singularities occur when inputs approach $[0, 0, 0]$.
2. **Double-Blind View Isolation**:
   - Test `GET /api/blind/poll?role=B` during Round 1 and ensure sender text, sender VAD, and model VAD are 100% absent from the JSON response.
3. **Real Dual-Client Physical Test**:
   - Launch `start.sh` and open two real browser windows (`/?role=A` and `/?role=B`).
   - Confirm Role A locks to Client A, Role B locks to Client B.
   - Verify that VCV Rack (UDP 7001) audibly receives OSC and modulates the continuous generative soundscape in the physical room.
4. **Data Auditability**:
   - Verify that every turn appends complete, audit-ready JSON lines into `blind_test_log.jsonl`.
   - Confirm exported JSON and CSV on the Revelation Dashboard match the server log byte-for-byte.

