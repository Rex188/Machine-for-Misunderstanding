#!/usr/bin/env python3
"""
generate_summary_chart.py — 直接从 SQLite 数据库提取真实数据生成高保真总结图

特点：
1. 100% 信任数据库：直接读取 SQLite 中的真实 records，绕过浏览器前端 JS 缓存与 DOM 解析。
2. 绘制多轮意图-机器-感知三维连线轨迹（Valence-Arousal 投影）。
3. 绘制误解指标卡片（Mean Misunderstanding, Model Gap, Medium Gap, Drift）。
4. 绘制每一轮去遮罩文字、真实模型 VADC、接收者感受与 8 通道 OSC 电压。
5. 自动在 macOS 弹窗预览或保存为 session_summary.png。
"""

import glob
import json
import os
import sys
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# 定位 blind_test 根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from db import Database


def get_latest_db():
    db_files = sorted(glob.glob(os.path.join(BASE_DIR, "data", "perf_*.db")))
    if not db_files:
        db_files = sorted(glob.glob(os.path.join(BASE_DIR, "data", "*.db")))
    if not db_files:
        raise FileNotFoundError("未在 data/ 目录下找到任何 SQLite 数据库！")
    return db_files[-1]


def generate_chart(db_path=None, output_path=None):
    if not db_path:
        db_path = get_latest_db()

    print(f"📖 正在从数据库加载数据: {db_path}")
    db = Database(db_path)
    conn = db.get_connection()

    sessions = conn.execute("SELECT * FROM sessions").fetchall()
    if not sessions:
        print("❌ 数据库中没有 Session记录")
        return

    session = dict(sessions[-1])
    sid = session["session_id"]
    full = db.get_full_session(sid)

    rounds = full.get("rounds", [])
    if not rounds:
        print("⚠️ 数据库中尚无已完成的轮次记录，跳过图表生成。")
        return

    input_events = full.get("input_events", [])
    model_runs = full.get("model_runs", [])
    markers = full.get("markers", [])
    receiver_responses = full.get("receiver_responses", [])
    metrics_list = full.get("metrics", [])

    print(f"✓ 成功读取 Session: {sid} (共 {len(rounds)} 轮)")

    # ── 开始绘图 ──────────────────────────────────────────────────────────────
    plt.style.use("dark_background")
    num_rounds = max(len(rounds), 1)
    fig_w = max(16, int(4.0 * num_rounds))
    fig = plt.figure(figsize=(fig_w, 10.5), facecolor="#090a0f")

    # 创建网格布局：左侧轨迹图，右上方指标卡片，下方逐轮审计明细
    gs = gridspec.GridSpec(2, 2, width_ratios=[1.2, 1.0], height_ratios=[1.2, 1.0], wspace=0.25, hspace=0.3)

    # ── 1. 左上：Valence-Arousal 多轮轨迹流动图 ───────────────────────────────
    ax_traj = fig.add_subplot(gs[0, 0])
    ax_traj.set_facecolor("#0d0f17")
    ax_traj.set_xlim(-0.05, 1.05)
    ax_traj.set_ylim(-0.05, 1.05)
    ax_traj.set_xlabel("VALENCE (Pleasure / Aversion) →", fontsize=11, color="#8b949e", labelpad=8)
    ax_traj.set_ylabel("AROUSAL (Energy / Lethargy) ↑", fontsize=11, color="#8b949e", labelpad=8)
    ax_traj.set_title("AFFECTIVE TRAJECTORY IN UNIT SPACE (V-A)", fontsize=13, fontweight="bold", color="#00f2fe", pad=12)

    # 网格线与中轴
    ax_traj.axvline(0.5, color="#30363d", linestyle="--", linewidth=1)
    ax_traj.axhline(0.5, color="#30363d", linestyle="--", linewidth=1)
    ax_traj.grid(True, color="#21262d", linestyle=":", alpha=0.6)

    colors_round = ["#00f2fe", "#f472b6", "#34d399", "#fbbf24", "#818cf8", "#f87171", "#38bdf8", "#a3e635"]

    for idx, rnd in enumerate(rounds):
        inp = next((e for e in input_events if e.get("event_id") == rnd.get("input_event_id") or e.get("round_id") == rnd.get("round_id")), None)
        mod = next((m for m in model_runs if m.get("model_run_id") == rnd.get("model_run_id") or m.get("round_id") == rnd.get("round_id")), None)
        rec = next((r for r in receiver_responses if r.get("receiver_response_id") == rnd.get("receiver_response_id") or r.get("round_id") == rnd.get("round_id")), None)

        p_inp = inp.get("input_vadc") if inp else None
        p_mod = (mod.get("output") or {}) if mod else None
        p_rec = rec.get("receiver_vadc") if rec else None

        pts = []
        labels = []
        if p_inp:
            pts.append((p_inp["valence"], p_inp["arousal"]))
            labels.append(f"R{idx+1}:Input")
        if p_mod and "valence" in p_mod and "arousal" in p_mod:
            pts.append((p_mod["valence"], p_mod["arousal"]))
            labels.append(f"R{idx+1}:Model")
        if p_rec:
            pts.append((p_rec["valence"], p_rec["arousal"]))
            labels.append(f"R{idx+1}:Receiver")

        if len(pts) >= 2:
            xs, ys = zip(*pts)
            r_col = colors_round[idx % len(colors_round)]
            ax_traj.plot(xs, ys, linestyle="--", color=r_col, alpha=0.85, linewidth=2, zorder=2)

        # 绘制节点
        for (x, y), lbl in zip(pts, labels):
            if "Input" in lbl:
                c = "#00f2fe"
            elif "Model" in lbl:
                c = "#a855f7"
            else:
                c = "#f59e0b"
            ax_traj.scatter(x, y, color=c, s=120, edgecolors="#ffffff", linewidth=1.5, zorder=3)
            ax_traj.annotate(lbl, (x, y), textcoords="offset points", xytext=(6, 6), color="#e6edf3", fontsize=9, fontweight="bold")

    # ── 2. 右上：累计核心科学指标卡片 ─────────────────────────────────────────
    ax_metrics = fig.add_subplot(gs[0, 1])
    ax_metrics.set_facecolor("#0d0f17")
    ax_metrics.axis("off")
    ax_metrics.set_title("CUMULATIVE MISUNDERSTANDING METRICS", fontsize=13, fontweight="bold", color="#a855f7", pad=12)

    # 计算均值
    avg_total = sum(m.get("raw_distance", {}).get("total", 0) for m in metrics_list) / max(len(metrics_list), 1)
    avg_conf = sum(m.get("confidence_adjusted_distance", {}).get("total", 0) for m in metrics_list) / max(len(metrics_list), 1)
    avg_mod = sum(m.get("raw_distance", {}).get("model", 0) for m in metrics_list) / max(len(metrics_list), 1)
    avg_med = sum(m.get("raw_distance", {}).get("medium", 0) for m in metrics_list) / max(len(metrics_list), 1)
    last_drift = next((m.get("inter_round_drift") for m in reversed(metrics_list) if m.get("inter_round_drift") is not None), None)

    drift_str = f"{last_drift:.3f}" if last_drift is not None else "N/A"
    metrics_text = (
        f"SESSION IDENTIFIER :  {sid}\n"
        f"STATUS             :  {session.get('status')} (Max Rounds: {session.get('max_rounds')})\n"
        f"────────────────────────────────────────────────────────\n\n"
        f"■ MEAN MISUNDERSTANDING (TOTAL)        :  {avg_total:.3f}\n"
        f"  Euclidean distance across Unit Cube  (Input ↔ Listener)\n\n"
        f"■ CONFIDENCE-ADJUSTED TOTAL           :  {avg_conf:.3f}\n"
        f"  Modulated by certainty weight factor\n\n"
        f"■ MACHINE TRANSLATION GAP (MODEL)     :  {avg_mod:.3f}\n"
        f"  Input phenomenological intent vs LLM acoustic params\n\n"
        f"■ ACOUSTIC MEDIUM GAP (PERCEPTION)    :  {avg_med:.3f}\n"
        f"  Synthesis modulation vs Listener somatic intake\n\n"
        f"■ INTER-ROUND SOMATIC DRIFT           :  {drift_str}\n"
        f"  Conversational trajectory drift across speaker handoffs\n\n"
        f"■ TOTAL COMPLETED ROUNDS               :  {len(rounds)} / {session.get('max_rounds', 3)}"
    )

    ax_metrics.text(0.05, 0.90, metrics_text, fontsize=11, fontfamily="monospace", color="#e6edf3", verticalalignment="top", linespacing=1.3)

    # ── 3. 下半部：逐轮真实审计明细表 ─────────────────────────────────────────
    ax_audit = fig.add_subplot(gs[1, :])
    ax_audit.set_facecolor("#0d0f17")
    ax_audit.axis("off")
    ax_audit.set_title("ROUND-BY-ROUND UNMASKED TRACE (TRUTH FROM DATABASE)", fontsize=13, fontweight="bold", color="#34d399", pad=12)

    col_w = 1.0 / max(len(rounds), 1)
    for idx, rnd in enumerate(rounds):
        inp = next((e for e in input_events if e.get("event_id") == rnd.get("input_event_id") or e.get("round_id") == rnd.get("round_id")), None)
        mod = next((m for m in model_runs if m.get("model_run_id") == rnd.get("model_run_id") or m.get("round_id") == rnd.get("round_id")), None)
        mark = next((mk for mk in markers if mk.get("marker_id") == rnd.get("marker_id") or mk.get("round_id") == rnd.get("round_id")), None)
        rec = next((r for r in receiver_responses if r.get("receiver_response_id") == rnd.get("receiver_response_id") or r.get("round_id") == rnd.get("round_id")), None)
        met = next((m for m in metrics_list if m.get("round_id") == rnd.get("round_id")), None)

        inp_v = inp.get("input_vadc", {}) if inp else {}
        mod_v = (mod.get("output") or {}) if mod else {}
        rec_v = rec.get("receiver_vadc", {}) if rec else {}
        voltages = (mark.get("acoustic_state") or {}).get("voltages", {}) if mark else {}

        raw_dist = met.get("raw_distance", {}) if met else {}

        import textwrap
        inp_text = textwrap.fill(f'"{inp.get("text", "")}"' if inp else 'N/A', width=38)
        rec_text = textwrap.fill(f'"{rec.get("somatic_shift", "")}"' if rec else 'N/A', width=38)

        x_start = idx * col_w + 0.02
        r_text = (
            f"══ ROUND {idx + 1} AUDIT ══\n"
            f"Sender: {rnd.get('sender_id', '')[-1]} → Receiver: {rnd.get('receiver_id', '')[-1]}\n\n"
            f"1. SENDER INSCRIPTION:\n"
            f"{inp_text}\n"
            f"   V:{inp_v.get('valence', 0):.2f} A:{inp_v.get('arousal', 0):.2f} D:{inp_v.get('dominance', 0):.2f} C:{inp_v.get('confidence', 0):.2f}\n\n"
            f"2. MODEL INTERPRETATION (TRUE DB):\n"
            f"   V:{mod_v.get('valence', 0):.2f} A:{mod_v.get('arousal', 0):.2f} D:{mod_v.get('dominance', 0):.2f} C:{mod_v.get('confidence', 0):.2f}\n"
            f"   Voltages: timbre={voltages.get('timbre_v', 0):.1f}V, freq={voltages.get('frequency_v', 0):.1f}V\n\n"
            f"3. RECEIVER INTAKE:\n"
            f"{rec_text}\n"
            f"   V:{rec_v.get('valence', 0):.2f} A:{rec_v.get('arousal', 0):.2f} D:{rec_v.get('dominance', 0):.2f} C:{rec_v.get('confidence', 0):.2f}\n\n"
            f"► Round Dist: {raw_dist.get('total', 0):.3f} (Model: {raw_dist.get('model', 0):.3f})"
        )
        ax_audit.text(x_start, 0.95, r_text, fontsize=9.5, fontfamily="monospace", color="#c9d1d9", verticalalignment="top", linespacing=1.2)

    # ── 保存并展示 ────────────────────────────────────────────────────────────
    import shutil
    db_stem = os.path.splitext(os.path.basename(db_path))[0]
    db_dir = os.path.dirname(os.path.abspath(db_path))

    if not output_path:
        # 默认与数据库文件同目录、同名 (如 data/perf_20261003_105712.png)
        output_path = os.path.join(db_dir, f"{db_stem}.png")

    plt.savefig(output_path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"🎉 真实结果图已成功生成 (与数据库 ID 一致):")
    print(f"   ► {output_path}")

    # 同时同步一份到 session_summary.png 供即时快捷预览
    latest_shortcut = os.path.join(BASE_DIR, "session_summary.png")
    if os.path.abspath(output_path) != os.path.abspath(latest_shortcut):
        try:
            shutil.copyfile(output_path, latest_shortcut)
            print(f"   ► {latest_shortcut} (最新快捷副本)")
        except Exception:
            pass

    # 若 session_id 与 db 文件名不完全一致，额外保留一份以 sid 命名的副本方便按 Session 检索
    if sid and sid != db_stem:
        sid_copy = os.path.join(db_dir, f"{sid}.png")
        try:
            shutil.copyfile(output_path, sid_copy)
            print(f"   ► {sid_copy} (按 Session ID 归档)")
        except Exception:
            pass

    # 在 macOS 上自动打开预览
    if sys.platform == "darwin":
        os.system(f"open '{output_path}'")


if __name__ == "__main__":
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    generate_chart(db_arg)
