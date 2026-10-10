# Project 2 Workflow — A Machine for Misunderstanding

> [English](README.md) | **[简体中文](README.zh-CN.md)**

**一句话**:A 的现象学文本 → 黑箱解释模型 → VAD 向量 → OSC → VCV 声音。
本目录是 Project 2「A Machine for Misunderstanding」的 MVP 实现层(自包含)。实际运行结果见 [`运行记录.zh-CN.md`](运行记录.zh-CN.md)。

---

## 1. 文档结构

| 文件 | 角色 |
|---|---|
| `README.md` | 英文主文档：架构、映射数学公式与运行说明 |
| `README.zh-CN.md` | 本文件：中文架构与映射说明 |
| `llm_sound_interactive.py` | **【最终核心交互驱动】**: 接收文学/身体描述 → LLM 现象学解释 → Eurorack 物理电压计算 → 平滑 Glide 发送 OSC 至 7001 |
| `运行记录.zh-CN.md` | 实际运行结果与验收状态 |
| `llm_to_vad.py` | 文本 → VAD 基础模型接口 |
| `vad_to_osc.py` | VAD → OSC 一次性发送测试脚本 |
| `seq_to_osc.py` | seq 循环驱动器 (Watch 模式自动巡回) |
| `max_interface.maxpat` | Max 9 交互与状态可视化界面 |
| `generative template new mvp.vcv` | **【核心发声工程】**：完整 5 声部生成式 VCV Patch（Audible Instruments Plaits、Arp、NYSTHI ConstAddMult、Clocked、MixMaster、cvOSCcv） |
| `docs/VCV_跳线实操指南.md` | **跳线完全手册**：端口级精确走线指南、声部分离与物理电平调试说明 |
| `docs/声音映射与媒介协调器执行方案.md` | **系统方案与映射哲学**：从身体现象学到模块化声学的完整架构分析 |
| `project2.vcv` | 早期简单单声部验证 patch |
| `seq_input.txt` | Watch 模式追加输入文件 |
| `seq_log.jsonl` | 运行日志记录 |

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

### OSC 协议与 Eurorack 物理电压映射 (最终版本)

`llm_sound_interactive.py` 将模型解释出的 VADC 四维空间，通过非线性心理声学算法转换为真实 Eurorack 控制电压（-5V ~ +5V / 0V ~ 10V）：

| OSC 地址 | 发送电压范围 | 物理目标模块与端口 | 数值计算公式 (Algorithm) | 声学与概念理由 (Reasoning) |
|---|---|---|---|---|
| **`/param/timbre`** | `0.0V ~ 2.4V` | **Plaits (Macro Osc 2)** `MODE CV` | 依据实测：0.05V(正弦), 0.66V(FM金属), 2.1V(共振和弦) | 唤醒度 Arousal 驱动合成器算法质变，高压激昂下触发 FM 金属撕裂音 |
| **`/param/frequency`** | `-3.0V ~ +4.0V` | **Clocked** `BPM_INPUT` | `freq_v = -3.0 + 7.0 * (0.7*A + 0.3*D)` | 对应 50 BPM 到 220+ BPM，Arousal 决定心率冲动 |
| **`/param/amplitude`** | `+2.0V ~ +10.0V` | **VCA-1** `CV` | `amp_v = 2.0 + 8.0 * (0.35 + 0.50*A + 0.15*D)` | 抬高 2V 底限，A 占 0.5 权重，确保激烈情绪下绝不静音 |
| **`/param/envelope`** | `-5.0V ~ +5.0V` | **Plateau** `DECAY` / ADSR | `env_v = -5.0 + 10.0 * (0.5*(1-A) + 0.3*D + 0.2*(1-C))` | 低 A 低 D 时拉长大混响尾迹，制造未解之谜与空间消融 |
| **`/param/mode`** | `-4.0V ~ +2.0V` | **ScaleCV** `MODE_INPUT` | $V<0.25$:-2V(Phrygian), $V<0.45$:+1V(Minor), $V>0.65$:-4V(Major) | Valence 效价决定调式色彩（负压抑小调/弗里吉亚，正明朗大调） |
| **`/param/chord`** | `0.0V ~ 6.0V` | **DiatonicCV** `CHORD_INPUT` | `chord_v = round(6.0 * (0.6*A + 0.4*(1-D)))` | 对应 I 到 VII 级和弦，平稳为主和弦，紧张为属/减和弦 |
| **`/param/type`** | `0.0V ~ 2.0V` | **DiatonicCV** `TYPE_INPUT` | $C>0.75$:0V(三和弦), $C>0.45$:1V(七和弦), 否则 2V(九和弦) | 确信度 $C$ 决定和弦复杂度（确信=纯三和弦，犹豫迷茫=7th/9th） |
| **`/param/noise`** | `+2.0V ~ +10.0V` | **MixMaster** Track 5 Level CV | `noise_v = 2.0 + 8.0 * (0.15 + 0.85*A*(1.2 - 0.4*C))` | 高 Arousal 与低 Confidence 共同触发肺泡喘息与白噪咆哮 |

> 💡 **Arp 解耦设计 (Const Add)**：  
> 为防止 Arp 被 Plaits 的 Mode 切换牵连，在 `DiatonicCV` 到 `Arp` 的 Pitch 输入之间串联一个 **Const Add（如 Bogaudio Offset / Fundamental 8vert）**，注入 `+1.0V ~ +2.0V` 的恒定直流偏置，将 Arp 强制抬升 1~2 个八度，确保高频晶莹琵音与主 Pad 彻底分离。

---

## 4. 运行方式

### 主用交互式驱动（推荐）：
```bash
# 启动交互式 LLM 声音控制终端 (支持名著预设 1/2/3、90秒自动巡回 4、自定义输入 c)
python3 llm_sound_interactive.py
```

### 单条测试与流水线：
```bash
# 单条测试(发 4 条 OSC 后结束)
echo "我的身体往里缩，不敢动" | python3 llm_to_vad.py | python3 vad_to_osc.py

# seq 循环驱动器 (Watch 模式)
python3 seq_to_osc.py --watch seq_input.txt
```

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
