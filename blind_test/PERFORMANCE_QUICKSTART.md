# 表演使用 Quickstart（现场一键使用指南）

> **Project 2: A Machine for Misunderstanding**  
> 专为演出/展示现场设计的**无脑一键使用指南**。不需要手动配置环境变量、不需要记各种端口和 curl 命令，一条命令搞定全部。

---

## ⚡ 极速 3 步操作（现场演出只需看这里）

### 第 1 步：打开声音合成器（VCV Rack）
在 macOS 中双击打开你的 VCV 工程：
```text
/Users/rexli/Documents/Rex/portfolio/project2/workflow/generative template new mvp.vcv
```
- 确认其中的 `cvOSCcv` 模块接收端口为 **7001**；
- 检查声卡或监听耳机音量正常。

---

### 第 2 步：打开终端，直接运行一键脚本
打开任意一个终端窗口，复制并执行以下命令：

```bash
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
./launch_performance.sh
```

脚本会自动完成以下动作：
1. 自动连接 Miniforge `blindtest` 环境与 Metal MPS 加速；
2. 自动检查 VCV Rack 7001 端口；
3. 自动释放 7070 和 8080 端口；
4. 自动创建带时间戳的独立数据库文件并初始化会话；
5. 同时在后台启动 **API 服务 (7070)** 与 **Web 界面服务 (8080)**；
6. **自动在你的浏览器中弹开两个独立的窗口/标签页**；
7. 在终端屏幕上打印出本次生成的唯一 **Session ID** 和 **A/B 专用 Token**。

---

### 第 3 步：在弹出的两个网页窗口中填入凭据并开始

终端会打印出类似如下的绿色凭据块：
```text
======================================================================
🔑 本次演出的登录凭据：

   【Participant A (先发声 Sender)】
   Session ID : s_perf_20261003_103000
   Slot       : Participant A
   Token      : token-A-20261003_103000

   【Participant B (先聆听 Receiver)】
   Session ID : s_perf_20261003_103000
   Slot       : Participant B
   Token      : token-B-20261003_103000
======================================================================
```

1. **窗口 1（左侧屏幕 / A 同学）**：
   - 填入 Session ID
   - 选中 **Participant A**
   - 填入 Token A
   - 点击 **Connect to Session**，进入后点击 **Mark Ready**。

2. **窗口 2（右侧屏幕 / B 同学）**：
   - 填入相同的 Session ID
   - 选中 **Participant B**
   - 填入 Token B
   - 点击 **Connect to Session**，进入后点击 **Mark Ready**。

3. 双方都 Ready 之后，任一窗口点击 **Start Session**，表演正式开始！

---

## 🎭 演出交互流程速查（3 轮闭环）

系统会自动根据轮次倒换角色，界面会有清晰的高亮提示（无需人工干预）：

| 轮次 | Participant A (窗口 1) | Participant B (窗口 2) | 声音载波流动 |
| :--- | :--- | :--- | :--- |
| **Round 1** | **Sender (发声方)**：<br>输入即时的身体感受文本，调整自评 VAD 坐标滑块，点击 Transmit | **Receiver (受听方)**：<br>静默聆听音响中的生成声音 | 本地 Qwen 推理生成情感 VAD 并通过 8 通道 OSC 电压调制 VCV Rack 合成器 |
| | 等待受听方反馈 | **Receiver**：<br>记录感受到的身体移位（Somatic Shift），评估听到的 VAD 坐标，提交反馈 | 提交后双方界面进入投票框，双方点击 **Vote: Continue to Next Round** |
| **Round 2** | **Receiver (受听方)**：<br>静默聆听 | **Sender (发声方)**：<br>角色自动对调！B 作为发声方输入身体感受并 Transmit | 声音再次根据 B 的输入动态实时演进 |
| | **Receiver**：<br>记录反馈并提交 | 等待受听方反馈 | 双方点击 **Vote: Continue to Next Round** |
| **Round 3** | **Sender (发声方)**：<br>A 再次发声输入并 Transmit | **Receiver (受听方)**：<br>B 聆听并提交 | 达到第 3 轮最大轮次，系统自动切入 **Settlement（终局解密）** |

---

## 🌟 终局解密（Settlement & Revelation）
- 3 轮结束后，两个窗口都会自动进入 **FINAL SETTLEMENT & REVELATION** 面板；
- **双盲屏障彻底解开**：
  1. **Multi-Round Trajectory 画布**：清晰连线展示每一轮 `输入意图(青) → 机器参数(紫) → 听者感知(橙)` 的多维流动轨迹；
  2. **Cumulative Misunderstanding 指标矩阵**：大字显示整体误解距离（Mean Misunderstanding）、置信度加权偏差、机器转译鸿沟（Model Gap）、媒介衰减鸿沟（Medium Gap）以及对话跨轮漂移（Inter-round Drift）；
  3. **逐轮审计列表**：完全公开双方的文字、未遮罩的 LLM 思考与生成详情、真实的 8 通道 OSC 发送电压数据。
- 适合直接投屏给现场观众展示。

---

## 🛑 结束与重置

演出结束或需要进行下一场时：
1. 回到运行 `./launch_performance.sh` 的终端；
2. 直接按 **Ctrl + C**；
3. 脚本会自动清理关闭所有 Python 后台服务并释放 7070 / 8080 端口；
4. 如需进行下一场，直接再次运行 `./launch_performance.sh` 即可生成全新场次。
