# Quickstart — A Machine for Misunderstanding

> **[English](QUICKSTART.md)** | [简体中文](QUICKSTART.zh-CN.md)

> Get it running in 5 minutes. Interface contract: [README.md](portfolio/project2/workflow/README.md); run log: [run-log.md](run-log.md).

## 0. What You Need

- **Python 3** (standard library only, zero dependencies)
- **VCV Rack** + `cvOSCcv` module (In Port = **7001**)
- **DeepSeek API key**
- **(Optional) Max 9** — only for the interface input and the VAD/seq display

## 1. Set Up the API Key

The key is read from the environment, and requests connect **directly to api.deepseek.com, automatically bypassing the local proxy** (runs in any terminal; nothing to configure for NO_PROXY):

```bash
export DEEPSEEK_API_KEY=sk-...      # or ANTHROPIC_AUTH_TOKEN
```

If unset, it falls back to `env.ANTHROPIC_AUTH_TOKEN` in `~/.claude/settings.json`.

## 2. Start VCV

Open the VCV patch and confirm `cvOSCcv`'s **In Port = 7001** (the module resets to 7001 after every edit).

## 3. Start the Driver

```bash
cd portfolio/project2/workflow
python3 seq_to_osc.py --watch seq_input.txt
```

You should see `seq_to_osc ready → 127.0.0.1:7001 | ... watch: seq_input.txt`.

## 4. Feed Text

Three ways, pick one:

- **Primary (watch)**: append a line to `seq_input.txt` = the machine interprets one segment and weaves it into the loop:
  ```bash
  echo "我手心冒汗，想站起来走" >> seq_input.txt
  ```
- **Max UI**: open `max_interface.maxpat`, click lock (Cmd+I).
  - Preset buttons (hot / cool / shrink): click while locked = send;
  - Custom text: unlock, click the message box to edit, press enter, lock again, click it = send.
  - The right side shows VAD ×4 + current step / total steps / seconds remaining in real time.
- **Pure CLI**: preseed the seq `python3 seq_to_osc.py "我手心冒汗，想站起来走"`, or interactive stdin (one line per segment, blank line exits).

## 5. Verify

- For each fed segment the terminal shows: `[seq N] text → {'valence':…, 'arousal':…, 'dominance':…, 'confidence':…} | dwell X.Xs`
- VCV: pitch / brightness / loudness follow the text, gliding smoothly between anchors
- Max: VAD ×4, current step, seconds remaining refresh in real time (10 Hz)
- The machine **auto-cycles** between anchors; dwell varies with confidence (more uncertain = dwells longer). Append any time — new segments join the loop.

## Ports

| Port | Direction | Content |
|---|---|---|
| **7100** | Max → Python | `/text` + string (Max UI sends text) |
| **7200** | Python → Max | `/state` + 7 float @10Hz (VAD, current step, total steps, seconds remaining) |
| **7201** | Python → Max | `/step_text` (reserved, not used by the UI) |
| **7001** | Python → VCV | `/vad/valence|arousal|dominance|confidence` |

## Common Parameters

```bash
python3 seq_to_osc.py --glide 0.12              # anchor glide speed (0~1)
python3 seq_to_osc.py --dwell-min 3 --dwell-max 18   # dwell range per step (s)
python3 seq_to_osc.py --verbose                 # print every send (debug)
```

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Terminal `[seq N]` shows `{0.5, 0.5, 0.5, 0.0}` | key not read or network failure. Check stderr `llm_to_vad: request failed (…)` / `key not found` |
| No sound in VCV | is `cvOSCcv` In Port = 7001? is the audio device selected? |
| Port already in use | `lsof -i :7001` / `:7100` / `:7200` |
| Want a fixed dwell per step | `--dwell-min 6 --dwell-max 6` |
| Appending has no effect | make sure you **append** a line (`>>`), not overwrite (`>`) |

## Known Limitations

- **③ current-step text display removed (decision 2026-08-24)**: Max 9's `udpreceive` can't carry Chinese text. The UI = input + VAD/seq display; input is primarily watch-mode appends.
- **confidence doesn't go into VCV**: bridge-side only, decides dwell seconds per step.
- **6 dimensions not implemented**: protocol slots reserved; fill in once names are aligned with the teacher.
- Experimental data is auto-logged to `seq_log.jsonl` (the raw material for the reveal).
