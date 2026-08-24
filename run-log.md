# Run Log — 2026-08-24 (MVP Day 1 Acceptance)

> **[English](run-log.md)** | [简体中文](运行记录.zh-CN.md)

> Acceptance criteria: project MVP spec §5 (kept outside the repo). Raw data: [`seq_log.jsonl`](seq_log.jsonl).

---

## 1. This Session's Inputs & Machine Interpretations

One participant A gave two real body descriptions; the machine explained each into a VAD anchor and wove them into the seq in order:

| seq | A's text | valence | arousal | dominance | confidence | dwell |
|---|---|---|---|---|---|---|
| 1 | 我感觉很热，然后很闷，天气非常燥热，但是还能接受 | 0.4 | 0.7 | 0.3 | 0.6 | **9.0 s** |
| 2 | 突然就很凉快，然后我舒服得很，我希望听到很欢快的节奏 | 0.9 | 0.8 | 0.6 | 0.8 | **6.0 s** |

**The machine's interpretation is meaningful**:
- seq 1 "hot · stuffy · dry heat" → mildly negative (0.4), a bit agitated (0.7), passive (0.3); "still bearable" pulls it back from purely negative.
- seq 2 "cool · comfortable · upbeat rhythm" → positive (0.9), high energy (0.8); the machine **understood "upbeat rhythm" and pushed arousal to 0.8**.
- confidence reflects how self-consistent the text is: seq 1 is self-contradictory (dry heat vs. still bearable) → 0.6 (hesitant, dwells 9 s); seq 2 is clearly comfortable → 0.8 (decisive, dwells 6 s).

---

## 2. Sound Chain Verification (built through the morning)

| Step | Verification | Result |
|---|---|---|
| text → VAD | the two texts produce clearly opposite semantic outputs | ✅ |
| VAD → OSC | local UDP decoder received 4 `/vad/*` messages | ✅ |
| OSC → VCV | ch1 VAL → VCO pitch; switching the two texts → **clear pitch jump** | ✅ chain is real |
| all three params | valence→VCF / arousal→VCO / dominance→VCA all track the text | ✅ |
| seq loop | machine auto-cycles between the two anchors, dwell varies with confidence | ✅ |

---

## 3. Acceptance Status (vs. MVP spec §5)

| # | Criterion | Status |
|---|---|---|
| 1 | Difference is audible: two texts with different valence / arousal / dominance sound different in brightness, density, stability | ✅ verified |
| 2 | Chain is real: text → DeepSeek → (OSC) → VCV → audio, every step actually runs | ✅ verified |
| 3 | No clipping: a 60–90 s piece without obvious clipping, 6 dB headroom at the peak | ⏳ not done (Day 4 mixing) |
| 4 | A technical write-up: input texts, model outputs, mapping, patch, known issues — reproducible by others | ✅ this file + README |

**MVP core achieved**: the sound layer and chain authenticity are established; the remaining clipping control is a sound-design/mixing task.

---

## 4. Issues & Fixes (process log)

1. **WatchSource re-read bug (2026-08-24)**: in `--watch` mode each poll re-read the whole file, feeding old lines in as new input over and over (one sentence got interpreted 8 times). Fix: track the file offset, read only the appended bytes. **Lesson: the pipe (stdin) path passing tests does not mean watch mode works — test both input sources.**
2. **`vad_to_osc.py` `json.load` → `json.loads`**: the stdin branch reads a str, not a file.
3. **OSC port alignment**: send-side default port changed 9000 → 7001 to match cvOSCcv's In Port (that module auto-resets to 7001 after every edit).
4. **Bare-terminal all-neutral fallback bug (2026-08-24)**: running `seq_to_osc.py` in my own terminal returned all `{0.5, 0.5, 0.5, 0.0}`. Root cause: the shell's `http_proxy` points at local 127.0.0.1:9567, while `NO_PROXY` is only injected by Claude Code (absent in a bare terminal) → urllib sent the api.deepseek.com request to the local proxy, which can't reach DeepSeek → every segment fell into the failure fallback. Fix: `llm_to_vad.py` uses an empty `ProxyHandler` to force a direct connection, no longer depending on the shell environment; the failure path now prints a stderr hint instead of silently returning neutral. **Lesson: code must not depend on the dev environment's shell variables.**
5. **Max `udpreceive` can't carry text (2026-08-24)**: the "current step's raw text" never displayed. The user pasted the Max console errors — `OSC packet size (43/79/82) not a multiple of 4 bytes: dropping` + `Bad message name string: Unreasonably long string` — decisive evidence: **Max 9's `udpreceive` parses every UDP packet as OSC; non-4-byte-aligned packets are dropped, and Chinese OSC strings are dropped as absurdly long message names**. So both the raw-text packet and the raw-OSC Chinese string die on the same parser (`/state` is a 48-byte aligned float packet, which is why it has always worked). Fix: send the text over standard OSC `/step_text` to a **separate port 7201**, received by the OSC-specialized `osc.udpreceive` + `route /step_text` on the Max side (leaving the healthy `/state` line on 7200 untouched). **Lesson: `udpreceive` ≠ a general UDP receiver; it's a strict OSC parser — for strings/Chinese you must use the osc.* family.**
6. **`osc.udpreceive` doesn't exist locally (2026-08-24)**: `osc.udpreceive: No such object` — the osc.* extension package is not installed/enabled. **Pivot: bypass UDP strings entirely.** Max stores the text into a local `coll` (index = send order = seq index); Python already broadcasts the current seq index as the 5th float of `/state`; `coll get <seq_idx>` looks the text up for display; `prepend append` stores, `prepend get` queries — zero strings cross UDP, only core objects. Limitation: text appended via the watch file never enters the coll, so ③ doesn't show it. **Lesson: if a working float channel + a local table can solve it, don't build a new transport; and confirm an object exists in the current environment before designing a protocol around it.**

---

## 5. Known Issues (left for the next phase)

- **Max ③ "current step's text" display: decision — not fixing (2026-08-24)**. After multiple repair rounds (`udpreceive` drops non-OSC/Chinese strings → `osc.udpreceive` not installed → coll local-table approach), this is an environment limitation + a nice-to-have, not worth more effort. **Input switches to `seq_input.txt` watch-appending** (equivalent to the Max input, and scriptable). The `coll` chain (`prepend append` / `coll` / `prepend get`) was also removed from the on-disk maxpat; the UI is back to pure "input + VAD/seq display" (28 boxes, no dangling wires).
- **Model non-determinism**: repeated calls on the same text drift slightly (temperature 0.3). For demos use fixed comparison texts; for the formal experiment, pin the model version and log every output.
- **Real-time latency**: each text feed adds ~1–2 s of LLM interpretation delay; the loop advances at roughly "one 6–10 s segment + glide".
- **confidence doesn't go into VCV**: bridge-side only, decides dwell seconds. To give it an audible role inside the patch, wire it elsewhere (e.g., drive a clock/LFO).
- **6 dimensions not implemented**: the protocol reserves slots; fill in once the names are aligned with the teacher.
