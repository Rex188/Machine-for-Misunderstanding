#!/usr/bin/env python3
"""
web_controller_server.py — A Machine for Misunderstanding: Web 控制中枢与 VCV Rack 桥接后端
零外部依赖 (仅标准库: http.server, socket, urllib, json, threading)
"""

from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import mimetypes
import os
import socket
import struct
import sys
import threading
import time
import urllib.request

# 导入核心声学映射与预设
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_sound_interactive import (
    ENDPOINT,
    MODEL,
    PRESETS,
    PROGRESSION_TEMPLATES,
    SYSTEM_PROMPT,
    call_llm,
    compute_sound_elements,
    osc_msg,
)

SERVER_PORT = int(os.environ.get("WEB_PORT", 7070))
OSC_HOST = os.environ.get("OSC_HOST", "127.0.0.1")
OSC_PORT = int(os.environ.get("OSC_PORT", 7001))
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seq_log.jsonl")

# 共享运行时状态
STATE_LOCK = threading.Lock()
_init_voltages = compute_sound_elements({
    "valence": 0.5,
    "arousal": 0.5,
    "dominance": 0.5,
    "confidence": 0.7,
})

CURRENT_STATE = {
    "status": "online",
    "vcv_connected": True,
    "last_text": "System ready. Enter first-person somatic descriptions or select a literary excerpt.",
    "last_title": "System Ready",
    "vadc": {
        "valence": 0.5,
        "arousal": 0.5,
        "dominance": 0.5,
        "confidence": 0.7,
        "reasoning": "Standby baseline: suspended in neutral equilibrium.",
    },
    "voltages": _init_voltages,
    "progression_enabled": True,
    "progression_interval": 10.0,
    "progression_step": 0,
    "last_update": datetime.now().isoformat(),
}

# UDP Socket
UDP_SOCK = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_osc_dict(voltages: dict):
    """向 VCV Rack (UDP 7001 cvOSCcv) 发送 8 个通道控制电压"""
    mapping = {
        "/param/timbre": voltages.get("timbre_v", 0.0),
        "/param/frequency": voltages.get("frequency_v", 0.0),
        "/param/amplitude": voltages.get("amplitude_v", 5.0),
        "/param/envelope": voltages.get("envelope_v", 0.0),
        "/param/scale": voltages.get("mode_v", -4.0),
        "/param/mode": voltages.get("mode_v", -4.0),
        "/param/chord": voltages.get("chord_v", 0.0),
        "/param/type": voltages.get("type_v", 0.0),
        "/param/noise": voltages.get("noise_v", 2.0),
    }
    for addr, val in mapping.items():
        try:
            msg = osc_msg(addr, float(val))
            UDP_SOCK.sendto(msg, (OSC_HOST, OSC_PORT))
        except Exception as e:
            print(f"[OSC Error] {addr} -> {e}")


def log_interaction(title: str, text: str, vadc: dict, voltages: dict):
    """持久化记录交互到 seq_log.jsonl"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "title": title,
        "text": text,
        "vad": vadc,
        "voltages": voltages,
        "t": time.time(),
    }
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[Log Error] {e}")


def progression_worker():
    """和弦自主演进后台线程：按照当前调式的和弦序列自动循环推进"""
    while True:
        try:
            with STATE_LOCK:
                enabled = CURRENT_STATE.get("progression_enabled", True)
                interval = CURRENT_STATE.get("progression_interval", 2.5)
                progression = CURRENT_STATE.get("voltages", {}).get("progression", [])
                step = CURRENT_STATE.get("progression_step", 0)

            if enabled and progression and len(progression) > 1:
                next_step = (step + 1) % len(progression)
                chord_info = progression[next_step]
                degree_v = float(chord_info["degree"])
                type_v = float(chord_info["type"])
                chord_name = chord_info["name"]

                try:
                    msg_chord = osc_msg("/param/chord", degree_v)
                    UDP_SOCK.sendto(msg_chord, (OSC_HOST, OSC_PORT))
                    msg_type = osc_msg("/param/type", type_v)
                    UDP_SOCK.sendto(msg_type, (OSC_HOST, OSC_PORT))
                except Exception as e:
                    print(f"[Progression OSC Error] {e}")

                with STATE_LOCK:
                    CURRENT_STATE["progression_step"] = next_step
                    CURRENT_STATE["voltages"]["chord_v"] = degree_v
                    CURRENT_STATE["voltages"]["chord_desc"] = chord_name
                    CURRENT_STATE["voltages"]["type_v"] = type_v

            time.sleep(interval)
        except Exception as e:
            print(f"[Progression Worker Error] {e}")
            time.sleep(2.0)


class RackWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/state":
            self.send_json_response(CURRENT_STATE)
        elif self.path == "/api/presets":
            preset_list = [
                {"id": k, "title": v["title"], "text": v["text"]}
                for k, v in PRESETS.items()
            ]
            self.send_json_response({"presets": preset_list})
        elif self.path == "/api/history":
            history = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, "r", encoding="utf-8") as f:
                        lines = f.readlines()[-20:]  # 最近 20 条
                    for line in reversed(lines):
                        if line.strip():
                            history.append(json.loads(line))
                except Exception as e:
                    print(f"[History Read Error] {e}")
            self.send_json_response({"history": history})
        else:
            # 静态页面资源
            super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        data = json.loads(body) if body else {}

        if self.path == "/api/interpret":
            # 1. 文本分析 (DeepSeek LLM)
            text = data.get("text", "").strip()
            title = data.get("title", "自定义现象学描述")
            if not text:
                self.send_json_response({"error": "文本内容不能为空"}, status=400)
                return

            print(f"\n[Web] 收到解释请求: {text[:60]}...")
            vadc = call_llm(text)
            voltages = compute_sound_elements(vadc)

            # 2. 发送 OSC 至 VCV Rack
            send_osc_dict(voltages)

            # 3. 持久化日志与更新状态
            log_interaction(title, text, vadc, voltages)
            with STATE_LOCK:
                CURRENT_STATE["last_text"] = text
                CURRENT_STATE["last_title"] = title
                CURRENT_STATE["vadc"] = vadc
                CURRENT_STATE["voltages"] = voltages
                CURRENT_STATE["last_update"] = datetime.now().isoformat()

            self.send_json_response({
                "status": "success",
                "vadc": vadc,
                "voltages": voltages,
            })

        elif self.path == "/api/send_vadc":
            # 实时推子微调 VADC
            vadc_in = data.get("vadc", {})
            with STATE_LOCK:
                vadc = {
                    "valence": float(vadc_in.get("valence", CURRENT_STATE["vadc"]["valence"])),
                    "arousal": float(vadc_in.get("arousal", CURRENT_STATE["vadc"]["arousal"])),
                    "dominance": float(vadc_in.get("dominance", CURRENT_STATE["vadc"]["dominance"])),
                    "confidence": float(vadc_in.get("confidence", CURRENT_STATE["vadc"]["confidence"])),
                    "reasoning": vadc_in.get("reasoning", "手动实时参数调制。"),
                }
                voltages = compute_sound_elements(vadc)
                send_osc_dict(voltages)
                CURRENT_STATE["vadc"] = vadc
                CURRENT_STATE["voltages"] = voltages
                CURRENT_STATE["last_update"] = datetime.now().isoformat()

            self.send_json_response({
                "status": "success",
                "vadc": vadc,
                "voltages": voltages,
            })

        elif self.path == "/api/send_cv":
            # 单通道直接控制
            param = data.get("param")  # e.g. "/param/timbre"
            value = float(data.get("value", 0.0))
            if param:
                try:
                    msg = osc_msg(param, value)
                    UDP_SOCK.sendto(msg, (OSC_HOST, OSC_PORT))
                    with STATE_LOCK:
                        key_map = {
                            "/param/timbre": "timbre_v",
                            "/param/frequency": "frequency_v",
                            "/param/amplitude": "amplitude_v",
                            "/param/envelope": "envelope_v",
                            "/param/scale": "mode_v",
                            "/param/mode": "mode_v",
                            "/param/chord": "chord_v",
                            "/param/type": "type_v",
                            "/param/noise": "noise_v",
                        }
                        if param in key_map:
                            CURRENT_STATE["voltages"][key_map[param]] = round(value, 2)
                    self.send_json_response({"status": "success", "param": param, "value": value})
                except Exception as e:
                    self.send_json_response({"error": str(e)}, status=500)
            else:
                self.send_json_response({"error": "param missing"}, status=400)

        elif self.path == "/api/set_mode":
            mode_v = float(data.get("mode_v", -4.0))
            prog_info = PROGRESSION_TEMPLATES.get(mode_v, PROGRESSION_TEMPLATES[-4.0])
            with STATE_LOCK:
                CURRENT_STATE["voltages"]["mode_v"] = mode_v
                CURRENT_STATE["voltages"]["mode_desc"] = prog_info["mode_name"]
                CURRENT_STATE["voltages"]["progression"] = prog_info["chords"]
                CURRENT_STATE["progression_step"] = 0
                first_chord = prog_info["chords"][0]
                CURRENT_STATE["voltages"]["chord_v"] = float(first_chord["degree"])
                CURRENT_STATE["voltages"]["chord_desc"] = first_chord["name"]
                CURRENT_STATE["voltages"]["type_v"] = float(first_chord["type"])
            try:
                UDP_SOCK.sendto(osc_msg("/param/scale", mode_v), (OSC_HOST, OSC_PORT))
                UDP_SOCK.sendto(osc_msg("/param/mode", mode_v), (OSC_HOST, OSC_PORT))
                UDP_SOCK.sendto(osc_msg("/param/chord", float(first_chord["degree"])), (OSC_HOST, OSC_PORT))
                UDP_SOCK.sendto(osc_msg("/param/type", float(first_chord["type"])), (OSC_HOST, OSC_PORT))
            except Exception as e:
                print(f"[Set Mode OSC Error] {e}")
            self.send_json_response({"status": "success", "state": CURRENT_STATE})

        elif self.path == "/api/set_progression":
            with STATE_LOCK:
                if "enabled" in data:
                    CURRENT_STATE["progression_enabled"] = bool(data["enabled"])
                if "interval" in data:
                    CURRENT_STATE["progression_interval"] = float(data["interval"])
                if "step" in data:
                    step = int(data["step"])
                    progression = CURRENT_STATE.get("voltages", {}).get("progression", [])
                    if 0 <= step < len(progression):
                        CURRENT_STATE["progression_step"] = step
                        chord_info = progression[step]
                        CURRENT_STATE["voltages"]["chord_v"] = float(chord_info["degree"])
                        CURRENT_STATE["voltages"]["chord_desc"] = chord_info["name"]
                        CURRENT_STATE["voltages"]["type_v"] = float(chord_info["type"])
                        try:
                            UDP_SOCK.sendto(osc_msg("/param/chord", float(chord_info["degree"])), (OSC_HOST, OSC_PORT))
                            UDP_SOCK.sendto(osc_msg("/param/type", float(chord_info["type"])), (OSC_HOST, OSC_PORT))
                        except Exception as e:
                            print(f"[Step OSC Error] {e}")
            self.send_json_response({"status": "success", "state": CURRENT_STATE})

        else:
            self.send_json_response({"error": "Endpoint not found"}, status=404)

    def send_json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def start_server():
    os.makedirs(WEB_DIR, exist_ok=True)
    server_address = ("0.0.0.0", SERVER_PORT)
    httpd = HTTPServer(server_address, RackWebHandler)
    print(f"\n=======================================================")
    print(f"  ★ A Machine for Misunderstanding · Web 控制中枢 ★")
    print(f"  Web UI 访问入口 : http://localhost:{SERVER_PORT}")
    print(f"  VCV Rack OSC   : {OSC_HOST}:{OSC_PORT}")
    print(f"=======================================================\n")
    send_osc_dict(CURRENT_STATE["voltages"])
    # 启动和弦演进后台线程
    t = threading.Thread(target=progression_worker, daemon=True)
    t.start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Web Server] 正在关闭服务...")
        httpd.server_close()


if __name__ == "__main__":
    start_server()
