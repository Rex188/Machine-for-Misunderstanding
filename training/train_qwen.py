#!/usr/bin/env python3
"""
train_qwen.py — Qwen2.5-1.5B-Instruct LoRA 极速微调脚本
适配：单卡 RTX 4090 / 3090 / A10 (AutoDL)
耗时：7000 条样本约 5~8 分钟
"""

import json
import os
import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)

MODEL_NAME = os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
OUTPUT_DIR = "./output_qwen_vadc"
DATA_DIR = "./data"


def load_alpaca_dataset(file_path: str, tokenizer, max_length: int = 512):
    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    input_ids_list, attention_mask_list, labels_list = [], [], []

    for item in raw_data:
        instruction = item["instruction"]
        user_input = item["input"]
        output = item["output"]

        # 采用 Qwen2.5 官方 Chat 模板
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": user_input},
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        response = output + "<|im_end|>\n"

        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
        response_ids = tokenizer.encode(response, add_special_tokens=False)

        input_ids = prompt_ids + response_ids
        # 仅对 response 部分计算 loss（Prompt Masking）
        labels = [-100] * len(prompt_ids) + response_ids

        if len(input_ids) > max_length:
            input_ids = input_ids[:max_length]
            labels = labels[:max_length]

        attention_mask = [1] * len(input_ids)

        input_ids_list.append(input_ids)
        attention_mask_list.append(attention_mask)
        labels_list.append(labels)

    return Dataset.from_dict({
        "input_ids": input_ids_list,
        "attention_mask": attention_mask_list,
        "labels": labels_list,
    })


def main():
    print(f"🚀 正在加载基座模型: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    # 配置 LoRA
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    print("📊 正在处理数据集...")
    train_dataset = load_alpaca_dataset(os.path.join(DATA_DIR, "train.json"), tokenizer)
    val_dataset = load_alpaca_dataset(os.path.join(DATA_DIR, "val.json"), tokenizer)

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        gradient_accumulation_steps=2,
        learning_rate=2e-4,
        num_train_epochs=3,
        logging_steps=20,
        eval_strategy="epoch",
        save_strategy="epoch",
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        save_total_limit=2,
        dataloader_num_workers=4,
        warmup_ratio=0.05,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True),
    )

    print("🔥 开始训练...")
    trainer.train()

    print("💾 正在保存最终 LoRA 权重...")
    trainer.save_model(os.path.join(OUTPUT_DIR, "final_lora"))
    tokenizer.save_pretrained(os.path.join(OUTPUT_DIR, "final_lora"))
    print("🎉 训练完成！权重已保存至:", os.path.join(OUTPUT_DIR, "final_lora"))


if __name__ == "__main__":
    main()
