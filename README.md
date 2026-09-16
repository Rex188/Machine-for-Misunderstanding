# Project 2 Workflow — A Machine for Misunderstanding

> **[English](portfolio/project2/workflow/README.md)** | [简体中文](portfolio/project2/workflow/README.zh-CN.md)

**What it is**: A's phenomenological body text → a black-box interpretation model → VAD vector → OSC → VCV sound.
This directory is the MVP implementation layer of Project 2, **self-contained**. Run results: [run-log.md](run-log.md).

---

## 1. Project Structure

| File | Role |
|---|---|
| `README.md` | This file: structure, chain architecture, interface contract, how to run |
| `run-log.md` | Run log & acceptance status (2026-08-24, MVP Day 1) |
| `llm_to_vad.py` | **① text → VAD**. DeepSeek API for the MVP; swappable for a fine-tuned model (same-interface drop-in) |
| `vad_to_osc.py` | **② VAD → OSC**, one-shot send (single test) |
| `seq_to_osc.py` | **②′ seq loop driver**: append text → smooth glide + machine auto-cycle (primary) |
| `max_interface.maxpat` | **Max 9 UI**: message input (unlock to edit, lock to click) / preset buttons (clickable while locked) → Python; receives state → shows VAD + seq (③ text display removed, see §3) |
| `project2.vcv` | **VCV Rack patch** — the sound "mouth": VCO → VCF → VCA → AUDIO, driven by `/vad/*` OSC (In Port 7001) |
| `seq_input.txt` | Watch-mode input: append a line = add a seq step |
| `seq_log.jsonl` | Auto-log of every step (text + VAD + dwell), the raw material for the reveal |

---

## 2. Chain Architecture

```
┌────────── Max 9 UI (max_interface.maxpat) ─────────────┐
│  ① message input (unlock to edit, lock to click)        │
│     + preset buttons (clickable while locked)           │
│  ② displays VAD ×4 + step / total / remain (10 Hz)      │
└──────────────┬──────────────────────────────▲───────────┘
        /text (7100)                 /state (7200)
               │                      every 0.1 s
               ▼                      │
   seq_to_osc.py —— the brain: LLM explain + glide
                    + confidence-driven dwell + auto-cycle
               │
        /vad/* (7001)
               ▼
   VCV patch: VCO → VCF → VCA → AUDIO —— the mouth
```

A types in Max or appends a line → Python explains it into a VAD anchor, glides to it and loops → the sound plays in VCV while the state is drawn back onto the Max UI. **The black box becomes visible.**

---

## 3. Interface Contract

### VAD JSON (model output, `llm_to_vad.py`)

```json
{"valence": 0.4, "arousal": 0.7, "dominance": 0.3, "confidence": 0.6}
```

| Field          | Meaning                                                                       |
| -------------- | ----------------------------------------------------------------------------- |
| **valence**    | 0 = negative → 1 = positive                                                   |
| **arousal**    | 0 = calm → 1 = excited                                                        |
| **dominance**  | 0 = passive / out of control → 1 = in control                                 |
| **confidence** | 0 = uncertain → 1 = certain (the machine's confidence in this interpretation) |

**Failure behavior**: missing field / network error → neutral vector `{0.5, 0.5, 0.5, confidence: 0.0}` (sound stays neutral, no clipping).

### OSC Protocol & Eurorack Physical Voltage Mapping (Final Specification)

`llm_sound_interactive.py` converts the VADC psychological state into real Eurorack modular control voltages (-5V to +5V / 0V to 10V) via psychoacoustic algorithms:

| OSC Address | Voltage Output | Target Module & Port | Calculation Algorithm | Psychoacoustic & Conceptual Reasoning |
|---|---|---|---|---|
| **`/param/timbre`** | `0.0V ~ 2.4V` | **Plaits (Macro Osc 2)** `MODE CV` | Empirically calibrated: 0.05V(Sine), 0.66V(FM Metal), 2.1V(Chords/Modal) | Arousal switches Plaits' synthesis engines; intense agitation triggers metallic FM tearing |
| **`/param/frequency`** | `-3.0V ~ +4.0V` | **Clocked** `BPM_INPUT` | `freq_v = -3.0 + 7.0 * (0.7*A + 0.3*D)` | Sweeps 50 BPM to 220+ BPM; Arousal drives the visceral pulse rate |
| **`/param/amplitude`** | `+2.0V ~ +10.0V` | **VCA-1** `CV` | `amp_v = 2.0 + 8.0 * (0.35 + 0.50*A + 0.15*D)` | Firm 2V floor + 0.5 Arousal weight ensures loud punch without choking |
| **`/param/envelope`** | `-5.0V ~ +5.0V` | **Plateau** `DECAY` / ADSR | `env_v = -5.0 + 10.0 * (0.5*(1-A) + 0.3*D + 0.2*(1-C))` | Low Arousal & low Dominance expand 10s reverb tails, creating spatial dissolution |
| **`/param/mode`** | `-4.0V ~ +2.0V` | **ScaleCV** `MODE_INPUT` | $V<0.25$:-2V(Phrygian), $V<0.45$:+1V(Minor), $V>0.65$:-4V(Major) | Valence selects musical mode (dark Phrygian/Minor vs. radiant Major/Lydian) |
| **`/param/chord`** | `0.0V ~ 6.0V` | **DiatonicCV** `CHORD_INPUT` | `chord_v = round(6.0 * (0.6*A + 0.4*(1-D)))` | Selects chord degrees I to VII (tonic at rest, dominant/diminished at tension) |
| **`/param/type`** | `0.0V ~ 2.0V` | **DiatonicCV** `TYPE_INPUT` | $C>0.75$:0V(Triad), $C>0.45$:1V(7th), otherwise 2V(9th) | Confidence decides harmonic ambiguity (certainty=Triad, hesitation=7th/9th) |
| **`/param/noise`** | `+2.0V ~ +10.0V` | **MixMaster** Track 5 Level CV | `noise_v = 2.0 + 8.0 * (0.15 + 0.85*A*(1.2 - 0.4*C))` | High Arousal & low Confidence trigger physiological breathlessness & noise blast |

> 💡 **Arp Register Decoupling (Const Add)**:  
> To decouple the arpeggiator from Plaits' mode modulation, insert a **Const Add module (Bogaudio Offset / Fundamental 8vert)** between `DiatonicCV` and `Arp` pitch input with a `+1.0V ~ +2.0V` DC offset. This shifts Arp 1–2 octaves up into a pristine high-register constellation.

---

## 4. How to Run

### Primary Interactive LLM Driver (Recommended):
```bash
# Start the interactive LLM terminal driver (Presets 1/2/3, 90s auto-cycle 4, custom input c)
python3 llm_sound_interactive.py
```

### One-shot & Loop Pipelines:
```bash
# One-shot text test
echo "我的身体往里缩，不敢动" | python3 llm_to_vad.py | python3 vad_to_osc.py

# Auto-cycle loop driver (watch mode)
python3 seq_to_osc.py --watch seq_input.txt
```

```bash
# one-shot test (sends 4 OSC messages then exits)
echo "我的身体往里缩，不敢动" | python3 llm_to_vad.py | python3 vad_to_osc.py

# interactive seq (one line per text, blank line exits; the machine auto-cycles)
python3 seq_to_osc.py

# seq watch mode (append a line to seq_input.txt = add a step)
python3 seq_to_osc.py --watch seq_input.txt

# common parameters
python3 seq_to_osc.py --glide 0.12            # anchor glide speed (0~1)
python3 seq_to_osc.py --dwell-min 3 --dwell-max 18   # dwell range per step (s)
python3 seq_to_osc.py --verbose               # print every send (debug)
```

### Running with the Max UI (recommended)

```bash
# 1. start the seq driver (listens on 7100 for text, broadcasts state on 7200)
python3 seq_to_osc.py --watch seq_input.txt

# 2. open max_interface.maxpat in Max, click lock (Cmd+I)
#    - locked: click a preset button (hot / cool / shrink) → text goes into the machine
#    - custom text: unlock (Cmd+I) → edit the message box, press enter → lock again (Cmd+I) → click the box = append a segment
#    - the right side shows VAD + seq state in real time
#    - after editing the patch: close WITHOUT saving and reopen — don't hot-reload an old instance
```

Environment variables: `DEEPSEEK_API_KEY` / `ANTHROPIC_AUTH_TOKEN` (or fallback `~/.claude/settings.json`) — the key is read even outside the shell; requests connect **directly to api.deepseek.com, automatically bypassing the local proxy** (no NO_PROXY needed, works in any terminal); `OSC_HOST` / `OSC_PORT` (default 127.0.0.1:7001, matches cvOSCcv); `OSC_RECV_PORT` (7100) / `OSC_STATE_PORT` (7200) / `OSC_TEXT_PORT` (7201).

---

## 7. Acceptance Status

See the run log [run-log.md](run-log.md).
