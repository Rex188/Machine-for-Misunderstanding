#!/usr/bin/env python3
"""
prepare_data.py — 数据清洗、VADC 降维投影与训练/验证集切分脚本

输入格式：
    {"text": "...", "vector": {"valence": ..., "arousal": ..., "dominance": ..., "embodiment": ..., "intentionality": ..., "source": ...}}

输出格式（标准 Alpaca / SFT 格式）：
    {
        "instruction": "You map a phenomenological body description to a VAD vector. Return ONLY a JSON object with keys valence, arousal, dominance, confidence, each a number between 0 and 1.",
        "input": "<phenomenological text>",
        "output": "{\"valence\": 0.25, \"arousal\": 0.35, \"dominance\": 0.4, \"confidence\": 0.62}"
    }

保证与下游 Max/MSP ↔ OSC 7001 ↔ VCV Rack 接口契约 100% 兼容，无需改动任何 OSC 协议。
"""

import argparse
import glob
import json
import os
import random


def compress_vector(v: dict) -> dict:
    valence = round(float(v["valence"]), 2)
    arousal = round(float(v["arousal"]), 2)
    dominance = round(float(v["dominance"]), 2)

    e = float(v.get("embodiment", 0.5))
    i = float(v.get("intentionality", 0.5))
    s = float(v.get("source", 0.5))

    # 现象学确信度合成公式：
    # 意向清晰度 (50%) + 具身确凿度 (35%) + 感知源明确度 (15%)
    source_clarity = abs(s - 0.5) * 2.0
    c_raw = 0.50 * i + 0.35 * e + 0.15 * source_clarity
    confidence = round(max(0.1, min(0.95, c_raw)), 2)

    return {
        "valence": valence,
        "arousal": arousal,
        "dominance": dominance,
        "confidence": confidence,
    }


SYSTEM_PROMPT = (
    "You map a phenomenological body description to a VAD vector. "
    "Return ONLY a JSON object with keys valence, arousal, dominance, confidence, "
    "each a number between 0 and 1. "
    "Never output emotion labels or any text outside the JSON."
)


def main():
    parser = argparse.ArgumentParser(description="清洗并切分现象学数据为 Qwen 微调指令集")
    parser.add_argument(
        "--input",
        nargs="+",
        default=[
            os.path.join(os.path.dirname(__file__), "..", "phenomenological_*.jsonl")
        ],
        help="输入的一或多个 jsonl 文件或 glob 模式",
    )
    parser.add_argument(
        "--output_dir",
        default=os.path.join(os.path.dirname(__file__), "data"),
        help="输出 train/val 目录",
    )
    parser.add_argument("--val_ratio", type=float, default=0.1, help="验证集比例 (默认 0.1)")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    random.seed(args.seed)

    input_files = []
    for pattern in args.input:
        matched = glob.glob(pattern)
        if matched:
            input_files.extend(matched)
        elif os.path.exists(pattern):
            input_files.append(pattern)

    if not input_files:
        print("未找到任何输入数据文件！")
        return

    print(f"找到 {len(input_files)} 个输入文件: {input_files}")

    all_samples = []
    skipped = 0

    for file_path in input_files:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    text = data["text"].strip()
                    vector = data["vector"]
                    target_vadc = compress_vector(vector)
                    
                    sample = {
                        "instruction": SYSTEM_PROMPT,
                        "input": text,
                        "output": json.dumps(target_vadc, ensure_ascii=False),
                    }
                    all_samples.append(sample)
                except Exception as e:
                    skipped += 1

    print(f"成功解析 {len(all_samples)} 条样本 (跳过无效行: {skipped})")

    random.shuffle(all_samples)
    val_count = int(len(all_samples) * args.val_ratio)
    val_samples = all_samples[:val_count]
    train_samples = all_samples[val_count:]

    train_path = os.path.join(args.output_dir, "train.json")
    val_path = os.path.join(args.output_dir, "val.json")

    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train_samples, f, ensure_ascii=False, indent=2)

    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(val_samples, f, ensure_ascii=False, indent=2)

    print(f"✅ 训练集: {len(train_samples)} 条 -> {train_path}")
    print(f"✅ 验证集: {len(val_samples)} 条 -> {val_path}")


if __name__ == "__main__":
    main()
