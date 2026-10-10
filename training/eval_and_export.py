#!/usr/bin/env python3
"""
eval_and_export.py — 评估微调后模型的 JSON 合规率与 VADC MAE 拟合精度，并可选合并导出完整模型
"""

import json
import os
import re
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
LORA_PATH = os.environ.get("LORA_PATH", "./output_qwen_vadc/final_lora")
VAL_FILE = "./data/val.json"
EXPORT_DIR = "./output_qwen_vadc/merged_model"


def extract_json(text: str) -> dict:
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(text)


def main():
    print(f"🔍 加载基座: {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    print(f"🧩 挂载 LoRA 权重: {LORA_PATH}")
    model = PeftModel.from_pretrained(base_model, LORA_PATH)
    model.eval()

    with open(VAL_FILE, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    # 随机抽 100 条验证集做快速评估
    test_samples = val_data[:100]
    print(f"📊 正在对 {len(test_samples)} 条验证样本进行推理评估...")

    valid_json_count = 0
    errors = {"valence": [], "arousal": [], "dominance": [], "confidence": []}

    keys = ("valence", "arousal", "dominance", "confidence")

    for idx, item in enumerate(test_samples):
        messages = [
            {"role": "system", "content": item["instruction"]},
            {"role": "user", "content": item["input"]},
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=100,
                temperature=0.1,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )

        gen_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        ground_truth = json.loads(item["output"])

        try:
            pred = extract_json(gen_text)
            valid_json_count += 1
            for k in keys:
                if k in pred:
                    errors[k].append(abs(float(pred[k]) - float(ground_truth[k])))
        except Exception:
            pass

        if idx < 3:
            print(f"\n--- 样本 {idx+1} ---")
            print("输入:", item["input"])
            print("真实标签:", item["output"])
            print("模型预测:", gen_text)

    json_rate = valid_json_count / len(test_samples) * 100
    print("\n" + "=" * 40)
    print(f"🎯 JSON 格式合规率: {json_rate:.1f}%")
    for k in keys:
        mae = sum(errors[k]) / len(errors[k]) if errors[k] else 0.0
        print(f"  {k:12s} 平均绝对误差 (MAE): {mae:.4f}")
    print("=" * 40)

    # 导出合并模型
    print(f"\n💾 正在合并 LoRA 并导出独立完整模型至: {EXPORT_DIR}")
    merged_model = model.merge_and_unload()
    merged_model.save_pretrained(EXPORT_DIR)
    tokenizer.save_pretrained(EXPORT_DIR)
    print("✅ 完整模型导出完毕！可直接用于 Ollama/vLLM/llama.cpp 部署。")


if __name__ == "__main__":
    main()
