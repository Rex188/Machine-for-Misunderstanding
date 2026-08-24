# Project 2 Workflow — A Machine for Misunderstanding

> [English](portfolio/project2/workflow/README.md) | **[简体中文](portfolio/project2/workflow/README.zh-CN.md)**

**一句话**:A 的现象学文本 → 黑箱解释模型 → VAD 向量 → OSC → VCV 声音。
本目录是 Project 2「A Machine for Misunderstanding」的 MVP 实现层(自包含)。实际运行结果见 [`运行记录.zh-CN.md`](运行记录.zh-CN.md)。

---

## 1. 文档结构

| 文件 | 角色 |
|---|---|
| `README.md` | 本文件(英文主文档):目录结构、链路架构、接口契约、运行方式 |
| `运行记录.zh-CN.md` | 实际运行结果与验收状态(2026-08-24, MVP Day 1) |
| `llm_to_vad.py` | **① 文本 → VAD**。MVP 用 DeepSeek API;后续替换为自微调模型(**同接口 drop-in**) |
| `vad_to_osc.py` | **② VAD → OSC 一次性发送**(单条测试用) |
| `seq_to_osc.py` | **②′ seq 循环驱动器**:逐条追加文本 → 平滑滑动 + 机器自动循环(当前主用) |
| `max_interface.maxpat` | **Max 9 交互+可视化界面**:message 输入(解锁编辑,锁回点击)/ 预制按钮(锁定可点) → 发 Python;收状态 → 显示 VAD + seq(③ 文本显示已移除,见 §3) |
| `project2.vcv` | **VCV Rack 补丁** —— 声音「嘴」:VCO → VCF → VCA → AUDIO,由 `/vad/*` OSC 驱动(In Port 7001) |
| `seq_input.txt` | watch 模式喂文本:append 一行 = 追加一步 seq |
| `seq_log.jsonl` | 运行时自动记录每一步(文本 + VAD + dwell),**reveal 的原始材料** |

---

## 2. 链路架构

```
┌────────── Max 9 UI (max_interface.maxpat) ─────────────┐
│  ① message input (unlock to edit, lock to click)        │
│     + preset buttons (clickable while locked)           │
│  ② displays VAD ×4 + step / total / remain (10 Hz)      │
└──────────────┬──────────────────────────────▲───────────┘
        /text (7100)                 /state (7200)
               │                      every 0.1 s
               ▼                      │
   seq_to_osc.py —— the brain: LLM explain + glide
                    + confidence-driven dwell + auto-cycle
               │
        /vad/* (7001)
               ▼
   VCV patch: VCO → VCF → VCA → AUDIO —— the mouth
```

A 在 Max 界面打字/追加文本 → 文本进 Python 脑 → 机器解释成 VAD 锚点、滑过去、循环 → 声音在 VCV 响起,状态同时画回 Max 界面。**黑箱「看得见」**。

---

## 3. 接口契约

### VAD JSON(模型输出,`llm_to_vad.py`)

```json
{"valence": 0.4, "arousal": 0.7, "dominance": 0.3, "confidence": 0.6}
```

- **valence** 0=消极 → 1=积极
- **arousal** 0=平静 → 1=激动
- **dominance** 0=被动/失控 → 1=主导/在控
- **confidence** 0=不确定 → 1=确信(机器对本次解释的确信度)
- **失败行为**:缺字段 / 网络错误 → 中性向量 `{0.5, 0.5, 0.5, confidence: 0.0}`(声音保持中性,不爆音)

### OSC 协议(预留 6 槽位)

| 地址 | 类型 | 用途 |
|---|---|---|
| `/vad/valence` | float 0–1 | 音色明暗(VCF cutoff) |
| `/vad/arousal` | float 0–1 | 能量/密度(VCO pitch) |
| `/vad/dominance` | float 0–1 | 稳定/响度(VCA gain) |
| `/vad/confidence` | float 0–1 | 决定每步停留秒数(不进 VCV) |
| *(3 槽位预留)* | — | 未来新增维度,补槽位即可,链路不改 |

### Max 界面桥(`seq_to_osc.py` ↔ `max_interface.maxpat`)

| 端口 | 方向 | 消息 | 内容 |
|---|---|---|---|
| **7100** | Max → Python | `/text` + string | A 的文本(点按钮/回车触发) |
| **7200** | Python → Max | `/state` + 7 float | valence, arousal, dominance, confidence, 当前步, 总步数, 剩余秒(每 0.1s) |
| **7201** | Python → Max | `/step_text` + string(OSC) | 当前步原文(预留:等 Max 装了 osc 扩展包后启用;当前界面未用) |

**③ 当前解释的文本显示:已移除(2026-08-24 决策)**。Max 9 的 `udpreceive` 把所有 UDP 当 OSC 解析,承载不了中文文本;`osc.udpreceive` 需 osc 扩展包(本机未装)。判断为环境限制 + 非验收必需项,不再投入。**界面 = 输入 + VAD/seq 显示;输入主用 `seq_input.txt` watch 追加**(与 Max 输入等价且可脚本化)。

---

## 4. 三个声音参数与映射

| 向量维度 | 含义 | 映射到 | Why |
|---|---|---|---|
| **Valence** | 积极 ↔ 消极 | **音色明暗**(VCF cutoff) | 亮 = 正、暗 = 负,听感最直觉的效价对应 |
| **Arousal** | 安静 ↔ 激动 | **能量 / 密度**(VCO pitch) | 唤醒的本质是能量水平 |
| **Dominance** | 被动 ↔ 主导 | **稳定 / 响度**(VCA gain) | 支配 = 控制 vs 失控;正是黑箱的「失控层」 |

---

## 5. confidence 的用法(桥侧,不进 VCV)

`seq_to_osc.py` 用 confidence 决定**每步停留秒数**(`停留 = 3 + (1 − confidence) × 15`,可调 3~18s):

- 机器**越不确定 → 停留越久**(迟疑、徘徊)
- 机器**越确定 → 越果断推进**

黑箱解释者「犹不犹豫」的可听见表现。

---

## 6. 运行方式

```bash
# 单条测试(发 4 条 OSC 后结束)
echo "我的身体往里缩，不敢动" | python3 llm_to_vad.py | python3 vad_to_osc.py

# seq 交互式(每行一段文本,空行退出;机器自动循环)
python3 seq_to_osc.py

# seq watch 模式(往 seq_input.txt append 一行 = 追加一步)
python3 seq_to_osc.py --watch seq_input.txt

# 常用参数
python3 seq_to_osc.py --glide 0.12            # 锚点间滑动速度(0~1)
python3 seq_to_osc.py --dwell-min 3 --dwell-max 18   # 每步停留范围(秒)
python3 seq_to_osc.py --verbose               # 每次发送都打印(调试)
```

### 带 Max 界面跑(推荐玩法)

```bash
# 1. 起 seq 驱动器(自动监听 7100 收文本、广播 7200 状态)
python3 seq_to_osc.py --watch seq_input.txt

# 2. Max 里打开 max_interface.maxpat,点「lock」(Cmd+I)
#    - 锁定状态:点预制按钮(热/凉/缩)→ 文本进机器
#    - 自定义文本:解锁(Cmd+I)→ 点输入框改文字,回车 → 锁回(Cmd+I)→ 点输入框 = 追加一段
#    - 右侧实时显示 VAD + seq 状态
#    - 改了 maxpat 之后要:关掉(不保存)重新打开,别在旧实例上热载
```

环境变量:`DEEPSEEK_API_KEY` / `ANTHROPIC_AUTH_TOKEN`(或 `~/.claude/settings.json` 兜底)——key 不在 shell 里也能读到;请求**直连 api.deepseek.com,自动绕开本机代理**(无需 NO_PROXY,任何终端可跑);`OSC_HOST` / `OSC_PORT`(默认 127.0.0.1:7001,匹配 cvOSCcv);`OSC_RECV_PORT`(7100)/`OSC_STATE_PORT`(7200)/`OSC_TEXT_PORT`(7201)。

---

## 7. 验收状态

见 [`运行记录.zh-CN.md`](运行记录.zh-CN.md)。
