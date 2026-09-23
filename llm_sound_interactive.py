#!/usr/bin/env python3
"""
llm_sound_interactive.py — Project 2: LLM 现象学身体经验理解与声音四要素实时驱动器

工作流：
    输入文本 (名著切片 / 自由描述)
        ↓ ① DeepSeek LLM 现象学解释黑箱
    {valence, arousal, dominance, confidence, reasoning}
        ↓ ② VADC 排列组合声学算法
    {timbre, frequency, amplitude, envelope}
        ↓ ③ 平滑过渡 (Glide) + OSC 发送至 VCV Rack (端口 7001)
    驱动 Plaits, Clocked, VCA, Plateau 实时发声！
"""

from datetime import datetime
import json
import os
import socket
import struct
import sys
import time
import urllib.request

# ── 配置 ──────────────────────────────────────────────────────────────
ENDPOINT = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
OSC_HOST = "127.0.0.1"
OSC_PORT = 7001

SYSTEM_PROMPT = (
    "You are the interpretation engine of 'A Machine for Misunderstanding'. "
    "Your task is to analyze the given phenomenological body description and translate it into inner states and a bespoke 4-step chord progression:\n"
    "1. valence (0.0 to 1.0): 0 = severe bodily pain/repression/darkness, 1 = open/warm/radiant.\n"
    "2. arousal (0.0 to 1.0): 0 = low energy/hypothermic/near-paralysis, 1 = cardiac acceleration/spasm/extreme agitation.\n"
    "3. dominance (0.0 to 1.0): 0 = helpless/loss of agency/swallowed by surroundings, 1 = mastery/assertive/expansion.\n"
    "4. confidence (0.0 to 1.0): How certain are you about this interpretation?\n"
    "5. reasoning: A concise sentence in English explaining how the physical sensations led to this interpretation.\n"
    "6. chord_progression: An array of 4 bespoke chord steps narrating the bodily trajectory (onset -> tension -> transformation -> afterglow). "
    "Each element MUST be an object: {\"degree\": 0-6, \"type\": 0-2, \"name\": \"...\"}\n"
    "   - degree: 0 (I/i), 1 (ii), 2 (iii), 3 (IV), 4 (V), 5 (vi), 6 (vii).\n"
    "   - type: 0 (Triad), 1 (7th Chord), 2 (9th Chord).\n"
    "   - name: evocative English label, e.g. 'i (Subterranean Drift)', 'bVI (Ascending Hope)', 'bIII (Dawn Glimmer)', 'bVII (Resilient Breath)'.\n"
    "Return ONLY a valid JSON object."
)

PRESETS = {
    "1": {
        "title": "Yukio Mishima · The Temple of the Golden Pavilion (Mizoguchi: Spasm, Stutter, Inner Conflagration)",
        "text": "The key hesitated in the lock. My tongue seized up behind my teeth, the initial syllable lodged in my throat like a scorching, jagged stone. Inside, the Golden Temple was ablaze with unbearable beauty, yet to the outside world, I was merely a grimacing creature with a twitching jaw."
    },
    "2": {
        "title": "Yukio Mishima · Spring Snow (Kiyoaki: Melting Snow, Heat Loss, Dissolution)",
        "text": "Outside the carriage, spring snow fell in profusion, melting instantly against the back of my hand into piercingly icy droplets. Beneath the blanket, my breath grew shallower and colder, fingertips losing sensation, as though my entire flesh were dissolving inch by inch into the silent drifts."
    },
    "3": {
        "title": "William Faulkner · The Sound and the Fury (Benjy: Cold Gusts, Dancing Flames, Bone Shiver)",
        "text": "The door opened and the cold came in, but I could smell the fire. The firelight danced on the smooth floor, bright shapes spinning outward. I held the cold wire fence, trembling in the wind, with a hot surge shouting through the marrow of my bones."
    }
}


LOG_FILE = "seq_log.jsonl"


def log_entry(text: str, vadc: dict, sound: dict, title: str = "", preset_id: str = "custom", dwell: float = 0.0):
    """记录每一次解释与声音映射至日志文件，确保实验可审计、可复现。"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "preset_id": preset_id,
        "title": title or "自定义身体描述",
        "text": text,
        "vad": {
            "valence": vadc.get("valence"),
            "arousal": vadc.get("arousal"),
            "dominance": vadc.get("dominance"),
            "confidence": vadc.get("confidence"),
            "reasoning": vadc.get("reasoning", "")
        },
        "voltages": {
            "timbre_v": sound.get("timbre_v"),
            "frequency_v": sound.get("frequency_v"),
            "amplitude_v": sound.get("amplitude_v"),
            "envelope_v": sound.get("envelope_v"),
            "mode_v": sound.get("mode_v"),
            "mode_desc": sound.get("mode_desc"),
            "chord_v": sound.get("chord_v"),
            "chord_desc": sound.get("chord_desc"),
            "type_v": sound.get("type_v"),
            "type_desc": sound.get("type_desc"),
            "noise_v": sound.get("noise_v"),
            "bpm_estimated": sound.get("bpm_estimated")
        },
        "dwell": dwell,
        "t": time.time()
    }
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[Warning] 写入日志失败: {e}", file=sys.stderr)


API_KEY_DEFAULT = "sk-f94b9c4c09d34a08ab7289b5827afc17"


def get_api_key() -> str:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ["DEEPSEEK_API_KEY"]
    return API_KEY_DEFAULT



def call_llm(text: str) -> dict:
    key = get_api_key()
    if not key:
        print("[错误] 未找到可用 API Key，将使用本地物理模拟兜底！", file=sys.stderr)
        return {
            "valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5,
            "reasoning": "本地兜底：中性基准状态"
        }

    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }).encode()

    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=30) as resp:
            content = json.load(resp)["choices"][0]["message"]["content"]
        out = json.loads(content)
        return out
    except Exception as e:
        print(f"[API 请求异常: {e}]，回落到默认状态", file=sys.stderr)
        return {
            "valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5,
            "reasoning": f"请求失败 ({e})"
        }


PROGRESSION_TEMPLATES = {
    -4.0: {
        "mode_name": "Ionian Major (-4V · Helpless Resignation & Static Fate)",
        "chords": [
            {"degree": 0, "type": 0, "name": "I (Tonic · Forced Plastic Smile)"},
            {"degree": 5, "type": 0, "name": "vi (Submediant · Weary Compromise)"},
            {"degree": 3, "type": 0, "name": "IV (Subdominant · Hollow Openness)"},
            {"degree": 4, "type": 0, "name": "V (Dominant · Pendulum of Fate)"},
        ]
    },
    -3.0: {
        "mode_name": "Dorian (-3V · Jazz Poetics & Suspended Stroll)",
        "chords": [
            {"degree": 0, "type": 1, "name": "i7 (Min 7 · Quiet Space)"},
            {"degree": 3, "type": 1, "name": "IV7 (Dom 7 · Passing Breeze)"},
            {"degree": 1, "type": 1, "name": "ii7 (Min 7 · Solitary Wander)"},
            {"degree": 0, "type": 1, "name": "i7 (Min 7 · Meditative Stillness)"},
        ]
    },
    -2.0: {
        "mode_name": "Phrygian (-2V · Melancholic Hope & Latent Resilience)",
        "chords": [
            {"degree": 0, "type": 0, "name": "i (Tonic Minor · Subterranean Shadow)"},
            {"degree": 5, "type": 0, "name": "bVI (Major 6th · Ascending Hope)"},
            {"degree": 2, "type": 0, "name": "bIII (Major 3rd · Dawn Glimmer)"},
            {"degree": 6, "type": 0, "name": "bVII (Major 7th · Resilient Breath)"},
        ]
    },
    -1.0: {
        "mode_name": "Lydian (-1V · Surreal Levitation & Displaced Reverie)",
        "chords": [
            {"degree": 0, "type": 0, "name": "I (Tonic · Detached Reality)"},
            {"degree": 1, "type": 0, "name": "II (Major 2nd · Luminous Aurora)"},
            {"degree": 4, "type": 0, "name": "V (Dominant · Weightless Hover)"},
            {"degree": 0, "type": 1, "name": "Imaj7 (Maj 7 · Dissolving Dream)"},
        ]
    },
    0.0: {
        "mode_name": "Mixolydian (0V · Radiant Freedom & Dynamic Surge)",
        "chords": [
            {"degree": 0, "type": 0, "name": "I (Tonic · Pure Exuberance)"},
            {"degree": 6, "type": 0, "name": "bVII (Flat 7 · Carefree Pulse)"},
            {"degree": 3, "type": 0, "name": "IV (Subdominant · Soaring Horizon)"},
            {"degree": 0, "type": 0, "name": "I (Tonic · Ecstatic Return)"},
        ]
    },
    1.0: {
        "mode_name": "Aeolian Minor (+1V · Pure Sorrow & Solitary Dissolution)",
        "chords": [
            {"degree": 0, "type": 0, "name": "i (Tonic Minor · Solitary Descent)"},
            {"degree": 3, "type": 0, "name": "iv (Subdominant Minor · Muted Sigh)"},
            {"degree": 5, "type": 0, "name": "VI (Major 6th · Welled Tears)"},
            {"degree": 4, "type": 0, "name": "v (Dominant Minor · Gradual Thaw)"},
        ]
    },
    2.0: {
        "mode_name": "Locrian (+2V · Structural Collapse & Extremal Rupture)",
        "chords": [
            {"degree": 0, "type": 0, "name": "i° (Diminished · Fractured Base)"},
            {"degree": 1, "type": 0, "name": "bII (Flat 2 · Acute Tear)"},
            {"degree": 4, "type": 0, "name": "v° (Diminished 5 · Disordered Mind)"},
            {"degree": 6, "type": 1, "name": "vii°7 (Diminished 7 · Total Dissolution)"},
        ]
    },
}


def compute_sound_elements(vadc: dict) -> dict:
    """
    通过 VADC 计算真实的 Eurorack 物理控制电压 (-5V ~ +5V / 0V ~ 10V):
      1. Timbre: -5V ~ +5V (Plaits Timbre & Morph)
      2. Frequency: -3V ~ +4V (Clocked BPM CV，基准 0V=100BPM，+4V=220+BPM，-3V=50BPM)
      3. Amplitude: 2.0V ~ 10.0V (VCA-1 Level，全功率输出，绝不静音)
      4. Envelope: -5V ~ +5V (ADSR / Plateau 混响)
      5. Mode: -4.0V ~ +2.0V (ScaleCV 7 大中古调式)
      6. Chord Degree: 0.0V ~ 6.0V (DiatonicCV: 0V=I, 1V=ii, 2V=iii, 3V=IV, 4V=V, 5V=vi, 6V=vii°)
      7. Chord Type: 0.0V ~ 2.0V (DiatonicCV: 0V=Triad, 1V=7th, 2V=9th)
      8. Noise: 2.0V ~ 10.0V (控制 Track 5 噪声推子与过载)
    """
    v = float(vadc.get("valence", 0.5))
    a = float(vadc.get("arousal", 0.5))
    d = float(vadc.get("dominance", 0.5))
    c = float(vadc.get("confidence", 0.5))

    # 1. Plaits Engine/Mode 真实电压 (依据实测：0.0V ~ 2.4V 覆盖 8 大旋律音高模型):
    #    0.0V ~ 0.25V: Model 0 (纯正弦波 Sine)
    #    0.60V ~ 0.70V: Model 2 (实测 0.66V 黄金甜点位 · 2-Operator FM 金属调频撕裂声)
    #    1.20V ~ 1.40V: Model 4 (实测 1.25V 加法谐波 Harmonic Additive，温润华丽 Pad，绝不跑调)
    #    1.80V ~ 2.20V: Model 6 (实测 2.10V 四音和弦 Chords，极度暴躁、撕裂、毁灭专属)
    #    > 2.40V: 极度失控时探入 Noise / Percussive 粒子噪波引擎
    if a < 0.30:
        # 极冷、死寂、低唤醒 (如《春雪》): 纯正弦波 Model 0
        timbre_v = 0.05
    elif a < 0.65:
        # 中等唤醒/温和状态:
        if v >= 0.50:
            # 温暖、舒缓、明朗 -> Model 4 (加法谐波 1.25V，丰富纯净 Pad)
            timbre_v = 1.25
        else:
            # 忧郁冷清 -> Model 1 (Waveshaping 轻微折叠波形 0.35V)
            timbre_v = 0.35 + 0.25 * (1.0 - v)
    else:
        # 高唤醒激昂、高压或暴冲:
        if v < 0.35:
            # 负向高压痛苦:
            if a > 0.85 and d < 0.25:
                # 极端暴躁/撕裂/毁灭失控 -> 触发 2.10V (Model 6 狂暴和弦撕裂)
                timbre_v = 2.10
            else:
                # 压抑痛苦暴冲 -> 直击 0.66V (实测 FM 金属撕裂音！)
                timbre_v = 0.66
        else:
            # 正向充沛奔涌 (开心激昂、大和声) -> 稳稳保持 1.25V (Model 4 华丽谐波 Pad，不与外置和弦打架)
            timbre_v = 1.25

    # 极度失控时（Arousal 极高且 Dominance 极低且低确信），允许短暂破壁探入 Noise Mode (2.65V)
    if a > 0.88 and d < 0.15 and (1.0 - c) > 0.30:
        timbre_v = 2.65

    # 2. Frequency 真实电压 (-3.0V ~ +4.0V):
    freq_norm = max(0.0, min(1.0, 0.7 * a + 0.3 * d))
    freq_v = -3.0 + 7.0 * freq_norm       # -3V (超慢) 到 +4V (超快)
    bpm_estimated = int(50 + 170 * freq_norm)

    # 3. Amplitude 真实电压 (2.0V ~ 10.0V，满载高增益):
    amp_norm = max(0.0, min(1.0, 0.35 + 0.50 * a + 0.15 * d))
    amp_v = 2.0 + 8.0 * amp_norm         # 2V (底噪) 到 10V (0dB 满功率轰鸣)

    # 4. Envelope 真实电压 (-5V ~ +5V):
    env_norm = max(0.0, min(1.0, 0.5 * (1.0 - a) + 0.3 * d + 0.2 * (1.0 - c)))
    env_v = -5.0 + 10.0 * env_norm

    # 5. ScaleCV Mode: 调式色彩哲学映射 (覆盖完整 7 种中古调式)
    #    -4V: Ionian (完全无奈/强颜欢笑)
    #    -3V: Dorian (爵士诗意/微风悬置)
    #    -2V: Phrygian (伤中怀望/暗流韧性)
    #    -1V: Lydian (超脱幻象/离奇升四度)
    #     0V: Mixolydian (真正欢快/自由奔涌)
    #    +1V: Aeolian (纯粹哀伤/质朴眼泪)
    #    +2V: Locrian (精神崩塌/极端撕裂)
    if a > 0.88 and d < 0.20 and v < 0.25:
        # 极端狂暴崩塌 -> Locrian
        mode_v = 2.0
    elif d < 0.32 and a < 0.65:
        # 完全无奈、无力回天、被迫妥协的平静停滞 -> Ionian (自然大调 · 强颜欢笑的无菌塑料感)
        mode_v = -4.0
    elif v < 0.45 and (a >= 0.35 or d >= 0.30):
        # 伤感痛苦中蕴含希望、生命力与暗流韧性 -> Phrygian (伤中怀望)
        mode_v = -2.0
    elif v < 0.35 and a < 0.35:
        # 彻底的冰冷沉沦、无声消融、质朴哀伤 -> Aeolian Minor
        mode_v = 1.0
    elif v >= 0.60:
        if a >= 0.40:
            # 真实奔涌的活力与热度 -> Mixolydian (0V)
            mode_v = 0.0
        else:
            # 离奇、轻盈、超脱重力的白日梦 -> Lydian (-1V)
            mode_v = -1.0
    else:
        # 中性浮动、沉思漫步、诗意悬置 -> Dorian (-3V)
        mode_v = -3.0

    # 提取对应调式基本信息
    prog_info = PROGRESSION_TEMPLATES.get(mode_v, PROGRESSION_TEMPLATES[-4.0])
    mode_desc = prog_info["mode_name"]

    # 动态演进构建：优先采用 LLM 根据身体经验现象学推理出的专属和弦进行
    llm_prog = vadc.get("chord_progression")
    valid_prog = []
    if isinstance(llm_prog, list) and len(llm_prog) >= 3:
        for idx, item in enumerate(llm_prog[:6]):
            if isinstance(item, dict) and "degree" in item:
                d_idx = max(0, min(6, int(item.get("degree", 0))))
                t_idx = max(0, min(2, int(item.get("type", 0))))
                name = str(item.get("name", f"Step {idx+1}"))
                valid_prog.append({"degree": d_idx, "type": t_idx, "name": name})
    
    if len(valid_prog) >= 3:
        progression = valid_prog
    else:
        # 基于调式模板与 VADC 扰动生成动态和弦进行 (确保非硬编码死板)
        base_chords = prog_info["chords"]
        progression = []
        for i, ch in enumerate(base_chords):
            deg = ch["degree"]
            typ = ch["type"]
            # 若确信度较低 (迷茫犹疑)，在第 2 或第 3 步扩展为 7th 或 9th 和弦
            if c < 0.60 and i in (1, 2):
                typ = 1 if c > 0.35 else 2
            # 若唤醒度高，在第 2 步增加张力级数偏移
            if a > 0.70 and i == 2:
                deg = (deg + 2) % 7
            progression.append({
                "degree": deg,
                "type": typ,
                "name": ch["name"] if deg == ch["degree"] else f"Step {i+1} (Tension Shift)"
            })

    # Default to chord step 0
    first_chord = progression[0]
    chord_v = float(first_chord["degree"])
    chord_desc = first_chord["name"]
    type_v = float(first_chord["type"])
    type_names = ["Triad", "7th Chord", "9th Chord"]
    type_desc = type_names[int(type_v)]

    # 8. Noise Level: 严格按 2.0V ~ 10.0V 正电压输出！
    noise_norm = max(0.0, min(1.0, 0.15 + 0.85 * a * (1.2 - c * 0.4)))
    noise_v = 2.0 + 8.0 * noise_norm

    return {
        "timbre_v": round(timbre_v, 2),
        "frequency_v": round(freq_v, 2),
        "amplitude_v": round(amp_v, 2),
        "envelope_v": round(env_v, 2),
        "mode_v": mode_v,
        "mode_desc": mode_desc,
        "chord_v": chord_v,
        "chord_desc": chord_desc,
        "type_v": type_v,
        "type_desc": type_desc,
        "noise_v": round(noise_v, 2),
        "bpm_estimated": bpm_estimated,
        "progression": progression,
    }


def _pad(s: str) -> bytes:
    b = s.encode() + b"\x00"
    b += b"\x00" * ((4 - len(b) % 4) % 4)
    return b


def osc_msg(address: str, val: float) -> bytes:
    return _pad(address) + _pad(",f") + struct.pack(">f", float(val))


def send_to_vcv(sock, sound: dict, vadc: dict, glide_steps: int = 15, current_cache: dict = None):
    """向 VCV Rack 发送真实物理控制电压，支持平滑过渡 Glide。"""
    targets = {
        "/param/timbre": sound["timbre_v"],
        "/param/frequency": sound["frequency_v"],
        "/param/amplitude": sound["amplitude_v"],
        "/param/envelope": sound["envelope_v"],
        "/param/scale": sound["mode_v"],
        "/param/mode": sound["mode_v"],
        "/param/chord": sound["chord_v"],
        "/param/type": sound["type_v"],
        "/param/noise": sound["noise_v"],
        "/vad/valence": vadc.get("valence", 0.5),
        "/vad/arousal": vadc.get("arousal", 0.5),
        "/vad/dominance": vadc.get("dominance", 0.5),
        "/vad/confidence": vadc.get("confidence", 0.5),
    }

    if not current_cache:
        current_cache = {k: targets[k] for k in targets}

    # 平滑过渡 (Glide) 15 步，每步 0.05s
    for step in range(1, glide_steps + 1):
        alpha = step / glide_steps
        for addr, target_val in targets.items():
            start_val = current_cache.get(addr, target_val)
            interpolated = start_val + (target_val - start_val) * alpha
            sock.sendto(osc_msg(addr, interpolated), (OSC_HOST, OSC_PORT))
        time.sleep(0.05)

    for k in targets:
        current_cache[k] = targets[k]
    return current_cache


def print_dashboard(text: str, vadc: dict, sound: dict):
    print("\n" + "═" * 72)
    print(" 📖 【输入身体描述】")
    print(f"    {text}")
    print("─" * 72)
    print(" 🧠 【LLM 解释黑箱 (VADC)】")
    print(f"    Valence (效价)   : {vadc.get('valence'):.2f}  |  Arousal (唤醒)   : {vadc.get('arousal'):.2f}")
    print(f"    Dominance (支配) : {vadc.get('dominance'):.2f}  |  Confidence (置信): {vadc.get('confidence'):.2f}")
    print(f"    解释理由: {vadc.get('reasoning', '无')}")
    print("─" * 72)
    print(" ⚡ 【真实 Eurorack 电压输出 (-5V ~ +5V / 0V ~ 10V)】")
    print(f"    • Plaits Mode CV (引擎模式) : {sound['timbre_v']:+5.2f} V   [0.05V 正弦 ~ 0.66V FM金属撕裂 ~ 2.1V 和弦共振]")
    print(f"    • Frequency (Clocked BPM)   : {sound['frequency_v']:+5.2f} V   [BPM ~ {sound['bpm_estimated']}]")
    print(f"    • Amplitude (VCA-1 增益)    : {sound['amplitude_v']:+5.2f} V   [2V 基础 ~ 10V 满幅爆响]")
    print(f"    • Envelope (Plateau 混响)   : {sound['envelope_v']:+5.2f} V   [-5V 干爽 ~ +5V 弥散烟雾]")
    print(f"    • ScaleCV Mode (调式)       : {sound['mode_v']:+5.2f} V   [{sound['mode_desc']}]")
    print(f"    • DiatonicCV Chord (级数)   : {sound['chord_v']:+5.2f} V   [{sound['chord_desc']}]")
    print(f"    • DiatonicCV Type (类型)    : {sound['type_v']:+5.2f} V   [{sound['type_desc']}]")
    print(f"    • Noise Level (噪声推子)    : {sound['noise_v']:+5.2f} V   [2V 微弱空气感  ~  10V 蒸汽白噪咆哮]")
    print("═" * 72 + "\n")


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    state_cache = None

    print("=" * 70)
    print("   A Machine for Misunderstanding: LLM 现象学驱动器")
    print("   已就绪，正在监听 OSC 目标 127.0.0.1:7001 (VCV Rack)")
    print("=" * 70)

    while True:
        print("\n请选择测试模式：")
        print(" [1] 名著选段 1：《金阁寺》（口吃、痉挛、内心暴冲、极高压）")
        print(" [2] 名著选段 2：《春雪》（极寒、冰冷融化、消融沉沦、长残响）")
        print(" [3] 名著选段 3：《喧哗与骚动》（冷风、火光跳动、骨骼奔涌）")
        print(" [4] 90秒自动连续巡回（1 $\\rightarrow$ 2 $\\rightarrow$ 3，每段停留 30 秒）")
        print(" [c] 自定义输入一段身体现象学描述")
        print(" [q] 退出")
        choice = input("\n请输入选项 [1/2/3/4/c/q]: ").strip()

        if choice in ("q", "quit", "exit"):
            break

        if choice == "4":
            print("\n>>> 开始 90 秒自动巡回演示...")
            for pid in ["1", "2", "3"]:
                p = PRESETS[pid]
                print(f"\n▶ 正在推进到：{p['title']}")
                vadc = call_llm(p["text"])
                sound = compute_sound_elements(vadc)
                print_dashboard(p["text"], vadc, sound)
                log_entry(p["text"], vadc, sound, title=p["title"], preset_id=pid, dwell=28.0)
                state_cache = send_to_vcv(sock, sound, vadc, glide_steps=20, current_cache=state_cache)
                print(f"📝 运行状态已持久化写入: {LOG_FILE}")
                print(">>> 正在保持该状态，发声中... (停留 28 秒)")
                time.sleep(28)
            print("\n>>> 90秒演示完成！")
            continue

        title = "自定义输入"
        if choice in PRESETS:
            text = PRESETS[choice]["text"]
            title = PRESETS[choice]["title"]
            print(f"\n▶ 选中：{title}")
        elif choice == "c":
            text = input("\n请输入你的身体现象学描述 (例: 胸口发闷，指尖冰冷，感觉身体在下沉...): ").strip()
            if not text:
                continue
        else:
            text = choice

        print("\n⏳ 正在请求 LLM 进行身体现象学解释...")
        vadc = call_llm(text)
        sound = compute_sound_elements(vadc)
        print_dashboard(text, vadc, sound)
        log_entry(text, vadc, sound, title=title, preset_id=choice, dwell=0.0)
        state_cache = send_to_vcv(sock, sound, vadc, glide_steps=15, current_cache=state_cache)
        print(f"📝 运行状态已持久化写入: {LOG_FILE}")
        print("✅ OSC 指令已平滑注入 VCV Rack！")


if __name__ == "__main__":
    main()
