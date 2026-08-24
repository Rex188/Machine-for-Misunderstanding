#!/usr/bin/env python3
"""
vad_to_osc.py — workflow 第二段：VAD JSON → OSC → VCV（cvOSCcv）

从 stdin 或文件读 VAD JSON，向 VCV 发 4 条 OSC：
    /vad/valence     float 0–1
    /vad/arousal     float 0–1
    /vad/dominance   float 0–1
    /vad/confidence  float 0–1

用法（整条链路）：
    echo "一段现象学描述" | python3 llm_to_vad.py | python3 vad_to_osc.py
    python3 vad_to_osc.py vad.json
    python3 llm_to_vad.py "描述" -o vad.json && python3 vad_to_osc.py vad.json

目标：OSC_HOST=127.0.0.1 OSC_PORT=7001（cvOSCcv 的 In Port 默认/重置为 7001）
依赖：仅标准库（手写 OSC，无需 pip install）。
"""
import json
import os
import socket
import struct
import sys

HOST = os.environ.get("OSC_HOST", "127.0.0.1")
PORT = int(os.environ.get("OSC_PORT", "7001"))


def _pad(s: str) -> bytes:
    b = s.encode() + b"\x00"
    b += b"\x00" * ((4 - len(b) % 4) % 4)
    return b


def osc_message(address: str, *floats: float) -> bytes:
    """最小 OSC 消息：地址 + 类型标签 + 大端 float。"""
    tag = "," + "f" * len(floats)
    return _pad(address) + _pad(tag) + b"".join(struct.pack(">f", f) for f in floats)


def send(vad: dict) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for key in ("valence", "arousal", "dominance", "confidence"):
        sock.sendto(osc_message(f"/vad/{key}", float(vad[key])), (HOST, PORT))
        print(f"  /vad/{key:<10} → {float(vad[key]):.2f}  ->  {HOST}:{PORT}")
    sock.close()


def main() -> None:
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            vad = json.load(f)
    else:
        vad = json.loads(sys.stdin.read())
    for k in ("valence", "arousal", "dominance", "confidence"):
        if k not in vad:
            print(f"error: VAD 缺字段 {k}", file=sys.stderr)
            sys.exit(1)
    print("发送 OSC:")
    send(vad)


if __name__ == "__main__":
    main()
