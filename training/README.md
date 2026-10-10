# Project 2 Qwen 微调实操指南 (AutoDL 极速版)

> **核心原则**：下游 Max/MSP ↔ OSC 7001 ↔ VCV Rack **零改动**。输出严格遵循 `{"valence", "arousal", "dominance", "confidence"}`。

---

## 1. AutoDL 租机选择 (5分钟开箱)

1. **算力机型**：选择 **RTX 4090 (24GB)** 或 **RTX 3090 (24GB)** 单卡即可（约 1.5 ~ 2 元 / 小时）。
2. **基础镜像**：
   - `PyTorch 2.4.0` (或 2.1+)
   - `Python 3.10` / `CUDA 12.1`
   - `Ubuntu 22.04`
3. 启动机器后，直接进入 **JupyterLab** 或使用本地终端 SSH 连入。

---

## 2. 云端一键跑训 (3 步搞定)

在 AutoDL 终端依次复制执行以下命令：

### 第一步：开启学术加速并安装轻量依赖
```bash
# 开启 AutoDL 内置学术加速（下载模型与依赖极速）
source /etc/network_turbo

# 安装微调三件套 (不到1分钟)
pip install transformers peft datasets accelerate bitsandbytes
```

### 第二步：上传数据与训练脚本
将你本地 `portfolio/project2/training/` 目录下的内容上传到云端（或直接使用 git clone / FileZilla / Jupyter 上传）：
- `data/train.json`
- `data/val.json`
- `train_qwen.py`
- `eval_and_export.py`

### 第三步：启动微调 (RTX 4090 耗时约 5 分钟)
```bash
python3 train_qwen.py
```
> **训练表现**：3 个 Epoch，Batch Size 8，LoRA Rank 16。终端会实时打印 Loss 下降曲线。
> 训练完成后，权重自动保存在 `./output_qwen_vadc/final_lora`。

---

## 3. 评估指标与导出独立模型

训练完成后，直接运行评估与导出脚本：
```bash
python3 eval_and_export.py
```
终端会自动打印：
- **JSON 结构合规率**（目标 100%）
- **Valence / Arousal / Dominance / Confidence 各维度的 MAE 绝对误差**
- 并在 `./output_qwen_vadc/merged_model` 生成可独立脱机加载的完整模型权重。

---

## 4. 下游 OSC 零改动接入 (Drop-in Replacement)

微调模型部署后（如通过 Ollama 或本地 Python 启动服务）：
只需将本地 `workflow/llm_to_vad.py` 或 `llm_sound_interactive.py` 的：
```python
ENDPOINT = "http://localhost:11434/v1/chat/completions" # 或你的本地模型服务
MODEL = "qwen2.5-1.5b-vadc"
```
其输出的 JSON 格式与现有 DeepSeek API 完全一致，所有 Eurorack 物理电压计算、OSC 7001 广播以及 Max 9 可视化界面**完全不需要任何修改**！
