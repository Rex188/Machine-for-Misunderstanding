#!/usr/bin/env python3
"""
seq_to_osc.py — 进程 seq 循环驱动器:逐条追加文本 → 机器自动在锚点间循环

设计(Machine for Misunderstanding:一台自己运转、不断重新解释的机器):

    每喂一段 A 的现象学描述
        → LLM 压成 VAD 锚点 → 追加进 seq(按时间顺序积累)
        → 机器跳到新锚点,停留 f(confidence) 秒,然后自动滑向下一个锚点
        → 循环走完整个 seq 后回到第一段重来;随时可追加,新段编进循环

    confidence 决定「每多少秒循环」——每一步停留多久:
        越不确定(confidence 低)→ 这一步停留越久(迟疑、徘徊);
        越确定 → 越果断,快速推进。
    这是黑箱解释者「犹不犹豫」的可听见表现(每维都答 Why)。

    glide 让锚点之间的移动是平滑滑动,不是跳变;连续 ~10Hz 发送 /vad/*。

用法:
    python3 seq_to_osc.py                          # 交互式:每行一段文本,空行退出
    python3 seq_to_osc.py 文本1 文本2 ...           # 预置 seq,之后仍可追加
    python3 seq_to_osc.py --glide 0.12             # 锚点间滑动速度(0~1,默认 0.12)
    python3 seq_to_osc.py --dwell-min 3 --dwell-max 18  # 每步停留范围(秒,默认 3~18)
    python3 seq_to_osc.py --watch seq_input.txt    # 外部喂文本:往文件 append 一行即可
    python3 seq_to_osc.py --verbose                # 每次发送都打印(调试用)

依赖:仅标准库。复用 llm_to_vad.py(文本→VAD)与 vad_to_osc.py(OSC 编码)。
"""
import json
import os
import select
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_to_vad
from vad_to_osc import osc_message

HOST = os.environ.get("OSC_HOST", "127.0.0.1")
PORT = int(os.environ.get("OSC_PORT", "7001"))

# Max 界面桥:收文本(7100)、回传状态(7200)
RECV_PORT = int(os.environ.get("OSC_RECV_PORT", "7100"))
STATE_PORT = int(os.environ.get("OSC_STATE_PORT", "7200"))
TEXT_PORT = int(os.environ.get("OSC_TEXT_PORT", "7201"))  # /step_text 单独端口 → Max osc.udpreceive

TICK = 0.1            # 10 Hz 发送
GLIDE = 0.12          # 每 tick 向目标接近的比例(指数接近,锚点间平滑移动)
DWELL_MIN = 3.0       # confidence=1 时每步停留秒数(果断,快速推进)
DWELL_MAX = 18.0      # confidence=0 时每步停留秒数(迟疑,徘徊)
KEYS = ("valence", "arousal", "dominance", "confidence")
NEUTRAL = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seq_log.jsonl")


# ── 给 Max 用的 OSC 编解码(支持 float / string 参数)────────────────────
def _pad(s: str) -> bytes:
    b = s.encode() + b"\x00"
    b += b"\x00" * ((4 - len(b) % 4) % 4)
    return b


def osc_msg(address: str, *args) -> bytes:
    """OSC 消息:地址 + 类型标签 + 参数(每个参数 float 或 str)。"""
    tag = ","
    parts = []
    for a in args:
        if isinstance(a, str):
            tag += "s"
            p = a.encode() + b"\x00"
            p += b"\x00" * ((4 - len(p) % 4) % 4)
            parts.append(p)
        else:
            tag += "f"
            parts.append(struct.pack(">f", float(a)))
    return _pad(address) + _pad(tag) + b"".join(parts)


def osc_recv(data: bytes):
    """解析一条简单 OSC 消息,返回 (address, args)。仅支持 f/i/s 参数。"""
    def read_str(pos):
        end = data.find(b"\x00", pos)
        return data[pos:end].decode(errors="replace"), (end + 1 + 3) // 4 * 4
    addr, pos = read_str(0)
    tag, pos = read_str(pos)
    args = []
    for t in tag[1:]:
        if t == "s":
            v, pos = read_str(pos)
            args.append(v)
        elif t == "f":
            args.append(struct.unpack(">f", data[pos:pos + 4])[0]); pos += 4
        elif t == "i":
            args.append(struct.unpack(">i", data[pos:pos + 4])[0]); pos += 4
        else:
            pos += 4
    return addr, args


# ── 文本源:stdin 或 watch 文件,统一的 poll() 返回新到达的完整行 ────────
class StdinSource:
    def __init__(self):
        self.buf = ""
        self.eof = False

    def poll(self):
        if self.eof:
            return []
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if not r:
            return []
        chunk = os.read(sys.stdin.fileno(), 4096).decode(errors="replace")
        if not chunk:                      # EOF
            self.eof = True
            return []
        self.buf += chunk
        return self._emit()

    def _emit(self):
        new = []
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            new.append(line.strip())
        return new


class WatchSource:
    """外部喂文本:往 watch 文件里 append 一行 = 追加一步 seq。

    跟踪文件偏移,只读新增的字节(否则重读整个文件会把旧行一遍遍当新输入)。
    尾部无换行的残行会留在 buf 里,等下一行补齐。
    """

    def __init__(self, path):
        self.path = path
        self.offset = 0        # 已读到的字节位置
        self.buf = ""

    def poll(self):
        try:
            with open(self.path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size < self.offset:      # 文件被截断 → 从头开始
                    self.offset = 0
                    self.buf = ""
                elif size == self.offset:   # 没有新增
                    return []
                f.seek(self.offset)
                chunk = f.read(size - self.offset).decode(errors="replace")
                self.offset = size
        except FileNotFoundError:
            return []
        self.buf += chunk
        new = []
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            new.append(line.strip())
        return new


# ── seq 状态 ──────────────────────────────────────────────────────────
def glide_into(state: dict, target: dict, k: float) -> None:
    """把 state 向 target 推进 k 的比例。k 越小越迟缓。"""
    for key in KEYS:
        state[key] += (target[key] - state[key]) * k


def send_state(sock, state: dict) -> None:
    for key in KEYS:
        sock.sendto(osc_message(f"/vad/{key}", float(state[key])), (HOST, PORT))


def log_anchor(rec: dict) -> None:
    rec = dict(rec)
    rec["t"] = time.time()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> None:
    argv = sys.argv[1:]
    verbose = "--verbose" in argv
    glide = GLIDE
    dwell_min = DWELL_MIN
    dwell_max = DWELL_MAX
    preseed = []
    source = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--glide":
            glide = max(0.0, min(1.0, float(argv[i + 1]))); i += 2
        elif a == "--dwell-min":
            dwell_min = max(0.0, float(argv[i + 1])); i += 2
        elif a == "--dwell-max":
            dwell_max = max(0.0, float(argv[i + 1])); i += 2
        elif a == "--watch":
            source = WatchSource(argv[i + 1]); i += 2
        elif a == "--verbose":
            i += 1
        elif a.startswith("--"):
            print(f"未知参数: {a}", file=sys.stderr); i += 1
        else:
            preseed.append(a); i += 1
    if source is None:
        source = StdinSource()

    def dwell_of(conf: float) -> float:
        """confidence → 这一步停留秒数:越确定越快,越不确定越迟疑。"""
        return dwell_min + (1.0 - conf) * (dwell_max - dwell_min)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)      # → VCV(声音,7001)
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # → Max(状态,7200)
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # ← Max(文本,7100)
    recv_sock.bind((HOST, RECV_PORT))
    recv_sock.setblocking(False)

    state = dict(NEUTRAL)     # 当前滑动中的位置(声音此刻的值)
    target = dict(NEUTRAL)    # 当前锚点(要滑向哪)
    steps = []                # 积累的锚点:{seq_idx, text, vad, dwell}
    cur = -1                  # 当前步骤索引;-1 = 还没有任何文本
    t_step = time.monotonic()  # 当前步停留开始的时间
    seq_idx = 0

    def announce_step(i: int) -> None:
        """把当前步的文本推给 Max 界面(走独立端口 7201 → Max osc.udpreceive)。

        udpreceive 把所有 UDP 当 OSC 解析,非 4 字节对齐直接丢(纯文本包 43/79/82 字节
        全被 Drop);标准 OSC 字符串 → 单独端口 + osc.udpreceive 才稳。
        """
        state_sock.sendto(osc_msg("/step_text", steps[i]["text"]), (HOST, TEXT_PORT))

    def start_step(i: int) -> None:
        nonlocal target, t_step
        target = dict(steps[i]["vad"])
        t_step = time.monotonic()
        announce_step(i)

    def append_step(text: str) -> None:
        nonlocal seq_idx, cur
        seq_idx += 1
        vad = llm_to_vad.llm_to_vad(text)
        steps.append({"seq_idx": seq_idx, "text": text, "vad": vad,
                      "dwell": dwell_of(vad["confidence"])})
        cur = len(steps) - 1                 # 跳到最新一段
        start_step(cur)
        log_anchor({"seq": seq_idx, "text": text, "vad": vad, "dwell": steps[cur]["dwell"]})
        print(f"\n[seq {seq_idx}] {text[:28]}{'…' if len(text) > 28 else ''} → {vad}"
              f" | 停留 {steps[cur]['dwell']:.1f}s", flush=True)

    # 预置:从命令行文本开始 seq
    for text in preseed:
        append_step(text)

    print(f"seq_to_osc 就绪 → {HOST}:{PORT} | glide={glide} | 停留 {dwell_min:.0f}~{dwell_max:.0f}s"
          + (" | watch: " + source.path if isinstance(source, WatchSource) else " | 空行退出")
          + " | 每行一段文本追加进 seq,机器自动循环", flush=True)

    t_next = time.monotonic() + TICK
    while True:
        # 1) 收新文本 → 追加 + 跳过去
        for line in source.poll():
            if not line:
                # stdin 模式:空行 = 退出;watch 模式:忽略
                if isinstance(source, StdinSource) and not source.buf:
                    print("\n空行退出。seq 记录已存 seq_log.jsonl。", flush=True)
                    return
                continue
            append_step(line)

        # 1') 收 Max 界面发来的 /text 文本(拼回含空格的多 token)
        while True:
            try:
                data, _ = recv_sock.recvfrom(65535)
            except BlockingIOError:
                break
            addr, args = osc_recv(data)
            if addr == "/text":
                text = " ".join(p.strip() for p in args if isinstance(p, str)).strip()
                if text:
                    append_step(text)

        # stdin EOF → 退出(管道/文件喂完就停)
        if isinstance(source, StdinSource) and source.eof and not source.buf:
            print("\n输入结束。seq 记录已存 seq_log.jsonl。", flush=True)
            return

        # 2) 循环推进:当前步停留时间到 → 滑向下一个锚点(末尾回绕到第一段)
        if steps and time.monotonic() - t_step >= steps[cur]["dwell"]:
            cur = (cur + 1) % len(steps)
            start_step(cur)
            s = steps[cur]
            print(f"  → 循环至 [seq {s['seq_idx']}] {s['text'][:20]}{'…' if len(s['text']) > 20 else ''}"
                  f" | 停留 {s['dwell']:.1f}s", flush=True)

        # 3) 滑动 + 发送(glide 固定速度;confidence 只决定停留,不再调速)
        glide_into(state, target, glide)
        send_state(sock, state)
        if verbose:
            print(f"  {state}", flush=True)

        # 3') 把此刻状态广播给 Max 界面(/state 7 个 float)
        if steps:
            dwell_rem = max(0.0, steps[cur]["dwell"] - (time.monotonic() - t_step))
        else:
            dwell_rem = 0.0
        state_sock.sendto(
            osc_msg("/state",
                    state["valence"], state["arousal"], state["dominance"],
                    state["confidence"],
                    float(steps[cur]["seq_idx"] if steps else 0),
                    float(len(steps)), dwell_rem),
            (HOST, STATE_PORT))

        # 4) 对齐 tick
        t_next += TICK
        delay = t_next - time.monotonic()
        if delay > 0:
            time.sleep(delay)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止。seq 记录已存 seq_log.jsonl。", file=sys.stderr)
