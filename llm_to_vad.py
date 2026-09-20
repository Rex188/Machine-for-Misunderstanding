#!/usr/bin/env python3
"""
llm_to_vad.py — workflow 第一段：A 的现象学文本 → VAD 向量（接口契约）

契约：
    {text} → {valence, arousal, dominance, confidence}  各 0–1

MVP 用 DeepSeek API；后续微调模型同接口 drop-in 替换（只换 BASE_URL/MODEL/KEY）。

用法：
    python3 llm_to_vad.py "我的身体往里缩，肩膀提起来，呼吸变浅，停在胸口。"
    echo "一段描述" | python3 llm_to_vad.py          # 从 stdin 读
    python3 llm_to_vad.py 文本 > vad.json             # 存文件，喂给 Max

依赖：仅标准库（urllib）。
密钥：环境变量 DEEPSEEK_API_KEY 或 ANTHROPIC_AUTH_TOKEN（读 ~/.claude/settings.json 兜底）。
网络：请求直连 api.deepseek.com，自动绕过本机代理，不依赖 shell 的 NO_PROXY。
"""
import json
import os
import sys
import urllib.request

# ── 配置 ──────────────────────────────────────────────────────────────
ENDPOINT = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = (
    "You map a phenomenological body description to a VAD vector. "
    "Return ONLY a JSON object with keys valence, arousal, dominance, confidence, "
    "each a number between 0 and 1. "
    "valence = positive(1) to negative(0); "
    "arousal = calm(0) to excited(1); "
    "dominance = passive(0) to in-control(1). "
    "Never output emotion labels or any text outside the JSON."
)

# 契约字段与默认失败行为（MVP 规格：每维定义失败行为）
KEYS = ("valence", "arousal", "dominance", "confidence")
FALLBACK = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.0}

API_KEY_DEFAULT = "sk-f94b9c4c09d34a08ab7289b5827afc17"


def get_key() -> str:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ["DEEPSEEK_API_KEY"]
    return API_KEY_DEFAULT


def _opener():
    """DeepSeek 直连：空 ProxyHandler = 不走任何代理（绕开本机 127.0.0.1:9567）。

    裸终端里 urllib 会按 http_proxy 把请求丢给本机代理，而代理到不了
    api.deepseek.com → 一路中性兜底。这里强制直连，任何终端都能跑。
    """
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def llm_to_vad(text: str) -> dict:
    key = get_key()
    if not key:
        print("llm_to_vad: 未找到 key(环境或 ~/.claude/settings.json)，回落中性向量",
              file=sys.stderr)
        return dict(FALLBACK)  # 失败行为：回落到中性向量

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
    try:
        with _opener().open(req, timeout=60) as resp:
            content = json.load(resp)["choices"][0]["message"]["content"]
        out = json.loads(content)
    except Exception as e:
        print(f"llm_to_vad: 请求失败({type(e).__name__}: {e})，回落中性向量",
              file=sys.stderr)
        return dict(FALLBACK)  # 失败行为：网络/解析失败 → 中性向量

    # clamp 到 0–1，缺键补默认
    for k in KEYS:
        try:
            out[k] = max(0.0, min(1.0, float(out[k])))
        except (KeyError, TypeError, ValueError):
            out[k] = FALLBACK[k]
    return {k: out[k] for k in KEYS}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read().strip()
    if not text:
        print("usage: llm_to_vad.py \"一段现象学描述\"  |  echo 描述 | llm_to_vad.py", file=sys.stderr)
        sys.exit(1)
    result = llm_to_vad(text)
    print(json.dumps(result, ensure_ascii=False))
