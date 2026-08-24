# Project 2 Workflow — A Machine for Misunderstanding

> **[English](README.md)** | [简体中文](README.zh-CN.md)

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

| Field | Meaning |
|---|---|
| **valence** | 0 = negative → 1 = positive |
| **arousal** | 0 = calm → 1 = excited |
| **dominance** | 0 = passive / out of control → 1 = in control |
| **confidence** | 0 = uncertain → 1 = certain (the machine's confidence in this interpretation) |

**Failure behavior**: missing field / network error → neutral vector `{0.5, 0.5, 0.5, confidence: 0.0}` (sound stays neutral, no clipping).

### OSC Protocol (6 slots reserved)

| Address | Type | Purpose |
|---|---|---|
| `/vad/valence` | float 0–1 | timbre brightness (VCF cutoff) |
| `/vad/arousal` | float 0–1 | energy / density (VCO pitch) |
| `/vad/dominance` | float 0–1 | stability / loudness (VCA gain) |
| `/vad/confidence` | float 0–1 | decides dwell seconds per step (not sent into VCV) |
| *(3 slots reserved)* | — | for future dimensions; add a slot, chain unchanged |

### Max ↔ Python Bridge (`seq_to_osc.py` ↔ `max_interface.maxpat`)

| Port | Direction | Message | Content |
|---|---|---|---|
| **7100** | Max → Python | `/text` + string | A's text (triggered by clicking a button / pressing enter) |
| **7200** | Python → Max | `/state` + 7 float | valence, arousal, dominance, confidence, current step, total steps, seconds remaining (every 0.1 s) |
| **7201** | Python → Max | `/step_text` + string(OSC) | current step's raw text (**reserved** — enabled once the osc extension package is installed; the UI does not use it now) |

**③ Current-step text display: removed (decision 2026-08-24)**. Max 9's `udpreceive` parses every UDP packet as OSC and cannot carry Chinese text; `osc.udpreceive` requires the osc extension package (not installed here). Judged an environment limitation + a non-required nicety, no more effort spent. **The UI = input + VAD/seq display; input is primarily appended to `seq_input.txt` in watch mode** (equivalent to the Max input, and scriptable).

---

## 4. The Three Sound Parameters

| Dimension | Meaning | Maps to | Why |
|---|---|---|---|
| **Valence** | positive ↔ negative | **timbre brightness** (VCF cutoff) | bright = positive, dark = negative — the most intuitive auditory valence |
| **Arousal** | calm ↔ excited | **energy / density** (VCO pitch) | arousal is essentially energy level |
| **Dominance** | passive ↔ in control | **stability / loudness** (VCA gain) | dominance = control vs. losing control — exactly the black box's "loss-of-control" layer |

---

## 5. What Confidence Does (bridge-side, not into VCV)

`seq_to_osc.py` uses confidence to decide **how long each step dwells** (`dwell = 3 + (1 − confidence) × 15`, adjustable 3–18 s):

- the more **uncertain** the machine → the **longer** it lingers (hesitation)
- the more **certain** → the more decisively it moves on

An audible sign of how "hesitant" the black-box interpreter is.

---

## 6. How to Run

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
