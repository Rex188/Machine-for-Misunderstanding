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
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
OSC_HOST = "127.0.0.1"
OSC_PORT = 7001

SYSTEM_PROMPT = (
    "You are the interpretation engine of 'A Machine for Misunderstanding'. "
    "Your task is to analyze the given phenomenological body description and map it into a 4-dimensional inner state: "
    "1. valence (0.0 to 1.0): 0 = severe bodily pain/repression/darkness, 1 = open/warm/radiant. "
    "2. arousal (0.0 to 1.0): 0 = low energy/hypothermic/near-paralysis, 1 = cardiac acceleration/spasm/extreme agitation. "
    "3. dominance (0.0 to 1.0): 0 = helpless/loss of agency/swallowed by surroundings, 1 = mastery/assertive/expansion. "
    "4. confidence (0.0 to 1.0): How certain are you about this interpretation? (contradictory/hesitant text = low, clear physical sensation = high). "
    "Return ONLY a valid JSON object with keys: valence, arousal, dominance, confidence, reasoning. "
    "In 'reasoning', provide a concise sentence in Chinese explaining how the physical sensations led to this interpretation."
)

PRESETS = {
    "1": {
        "title": "《金阁寺》三岛由纪夫 · 沟口（口吃、喉部痉挛、内心暴冲）",
        "text": "钥匙在锁孔里迟疑。我的舌头在牙齿背后痉挛，第一个音节卡在喉管深处，像一块滚烫而粗糙的石头。内心的金阁在剧烈燃烧，但在外界看来，我只是一个张着嘴、面部抽搐的怪物。"
    },
    "2": {
        "title": "《春雪》三岛由纪夫 · 清显（雪融手背、体温流失、消融沉沦）",
        "text": "车窗外是漫天纷飞的春雪，落在手背上瞬间融化成刺骨的水滴。呼吸在毛毯里变得越来越轻、越来越冷，指尖失去知觉，整个肉身仿佛正一寸一寸融进无声的积雪深处。"
    },
    "3": {
        "title": "《喧哗与骚动》福克纳 · 班吉（冷风、火光跳动、骨骼里的奔涌）",
        "text": "门开了，冷风扑进来，但我能闻到火的温度。火光在光滑的木地板上跳舞，亮晃晃的花纹一圈圈荡开。我抓着铁丝网，身体在风里剧烈摇晃，骨头里全是一阵阵发烫的叫喊。"
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


def get_api_key() -> str:
    for env in ("DEEPSEEK_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        if os.environ.get(env):
            return os.environ[env]
    p = os.path.expanduser("~/.claude/settings.json")
    if os.path.exists(p):
        try:
            d = json.load(open(p))
            if d.get("env", {}).get("ANTHROPIC_AUTH_TOKEN"):
                return d["env"]["ANTHROPIC_AUTH_TOKEN"]
            if d.get("env", {}).get("DEEPSEEK_API_KEY"):
                return d["env"]["DEEPSEEK_API_KEY"]
        except Exception:
            pass
    return ""



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


def compute_sound_elements(vadc: dict) -> dict:
    """
    通过 VADC 计算真实的 Eurorack 物理控制电压 (-5V ~ +5V / 0V ~ 10V):
      1. Timbre: -5V ~ +5V (Plaits Timbre & Morph)
      2. Frequency: -3V ~ +4V (Clocked BPM CV，基准 0V=100BPM，+4V=220+BPM，-3V=50BPM)
      3. Amplitude: 2.0V ~ 10.0V (VCA-1 Level，全功率输出，绝不静音)
      4. Envelope: -5V ~ +5V (ADSR / Plateau 混响)
      5. Mode: -4.0V ~ +2.0V (ScaleCV: -4V=Major, -3V=Dorian, -2V=Phrygian, +1V=Minor, -1V=Lydian)
      6. Chord Degree: 0.0V ~ 6.0V (DiatonicCV: 0V=I, 1V=II, 2V=III, 3V=IV, 4V=V, 5V=VI, 6V=VII)
      7. Chord Type: 0.0V ~ 2.0V (DiatonicCV: 0V=Triad, 1V=7th, 2V=9th)
      8. Noise: -5V ~ +5V (0V~10V，控制 Track 5 噪声推子与过载)
    """
    v = float(vadc.get("valence", 0.5))
    a = float(vadc.get("arousal", 0.5))
    d = float(vadc.get("dominance", 0.5))
    c = float(vadc.get("confidence", 0.5))

    # 1. Plaits Engine/Mode 真实电压 (依据实测：0.0V ~ 2.4V 覆盖 8 大旋律音高模型):
    #    0.0V ~ 0.25V: Model 0 (纯正弦波 Sine)
    #    0.60V ~ 0.70V: Model 2 (实测 0.66V 黄金甜点位 · 2-Operator FM 金属调频撕裂声！)
    #    1.20V ~ 1.40V: Model 4 (加法谐波 Harmonic Additive)
    #    1.80V ~ 2.20V: Model 6/7 (四音和弦 Chords / 物理共振 Modal Resonator)
    #    > 2.40V: 极度暴冲时轻微探入 Noise / Percussive 打击乐噪波引擎
    if a < 0.30:
        # 极冷、死寂 (如《春雪》): 纯正弦波 Model 0
        timbre_v = 0.05
    elif a < 0.65:
        # 中等/明朗 (如温和状态): Model 1 (Waveshaping) 或 Model 4 (Harmonic)
        timbre_v = 0.35 + 1.0 * v
    else:
        # 高压、暴冲、痉挛 (如《金阁寺》):
        if v < 0.40:
            # 压抑痛苦暴冲 -> 直击 0.66V (实测 FM 金属撕裂音！)
            timbre_v = 0.66
        else:
            # 明亮充沛奔涌 (如《喧哗与骚动》) -> 2.10V (Model 7 物理共振马林巴 / 和弦)
            timbre_v = 2.10
    
    # 极度失控时（Arousal 极高且 Dominance 极低），允许短暂破壁探入 Noise Mode (2.6V)
    if a > 0.85 and d < 0.20 and (1.0 - c) > 0.25:
        timbre_v = 2.65  # 破壁进入打击乐/粒子噪波引擎！

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

    # 5. ScaleCV Mode: 根据 Valence 切换 7 种中古调式 (-4V ~ +2V)
    #    -4V: Ionian (大调) | -3V: Dorian | -2V: Phrygian | -1V: Lydian | +1V: Aeolian (自然小调)
    if v < 0.25:
        mode_v = -2.0  # 弗里吉亚 (Phrygian · 极度压抑、黑暗降二度)
        mode_desc = "Phrygian (-2V · 极度压抑黑暗)"
    elif v < 0.45:
        mode_v = 1.0   # 自然小调 (Aeolian · 忧郁感伤)
        mode_desc = "Aeolian Minor (+1V · 忧郁冷清)"
    elif v < 0.65:
        mode_v = -3.0  # 多利亚 (Dorian · 悬置中性)
        mode_desc = "Dorian (-3V · 悬置爵士漂浮)"
    elif v < 0.85:
        mode_v = -4.0  # 自然大调 (Ionian · 明朗开阔)
        mode_desc = "Ionian Major (-4V · 明亮舒展)"
    else:
        mode_v = -1.0  # 利底亚 (Lydian · 升四度梦幻)
        mode_desc = "Lydian (-1V · 极乐升华梦幻)"

    # 6. DiatonicCV Chord 级数 (0V ~ 6V):
    #    由 Arousal 和 Dominance 驱动：平稳选主和弦 (0V/I)，紧张选属/导/副和弦 (3V~6V)
    chord_degree = int(round(6.0 * (0.6 * a + 0.4 * (1.0 - d))))
    chord_degree = max(0, min(6, chord_degree))
    chord_names = ["I (主和弦)", "ii (二级)", "iii (三级)", "IV (下属)", "V (属和弦)", "vi (下中和弦)", "vii° (减七级)"]
    chord_v = float(chord_degree)

    # 7. DiatonicCV Chord Type (0V=Triad 三和弦, 1V=7th 七和弦, 2V=9th 九和弦):
    #    受犹豫度 (1-C) 驱动：确定时纯三和弦，犹豫迷茫时扩展为 7th/9th 复杂色彩和弦
    if c > 0.75:
        type_v = 0.0
        type_desc = "Triad (三和弦 · 纯正果断)"
    elif c > 0.45:
        type_v = 1.0
        type_desc = "7th (七和弦 · 情感饱满)"
    else:
        type_v = 2.0
        type_desc = "9th (九和弦 · 复杂犹豫迷茫)"

    # 8. Noise Level: 严格按 2.0V ~ 10.0V 正电压输出！
    #    低压/平静 -> 2.0V (微弱底噪空气感)
    #    高压/挣扎 -> 8.0V ~ 10.0V (狂暴白噪/蒸汽气流)
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
        "chord_desc": chord_names[chord_degree],
        "type_v": type_v,
        "type_desc": type_desc,
        "noise_v": round(noise_v, 2),
        "bpm_estimated": bpm_estimated,
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
