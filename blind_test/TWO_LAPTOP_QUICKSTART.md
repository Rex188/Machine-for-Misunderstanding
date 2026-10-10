# 双电脑现场表演 Quickstart（无脑操作指南）

> **Project 2: A Machine for Misunderstanding**  
> **现场架构**：
> - **电脑 A（你的主机）**：运行 Qwen 本地模型 + VCV Rack 合成器 + 数据库 + 网页/API 服务，音箱/声卡接在你的电脑上，担任 **Participant A**。
> - **电脑 B（对方副机）**：**无需配置任何 Python、VCV 或模型环境**，只需打开浏览器访问你的电脑局域网 IP，担任 **Participant B**。

---

## ⚡ 演出前 1 分钟极速准备（仅需两步）

### 步骤 1：两台电脑连入同一网络
- 将 **你的电脑** 和 **对方的电脑** 连接到同一个 **Wi-Fi**（或者你手机开一个个人热点，两台电脑都连上手机热点）。

### 步骤 2：在你的电脑上打开 VCV Rack
双击打开：
```text
/Users/rexli/Documents/Rex/portfolio/project2/workflow/generative template new mvp.vcv
```
- 确认其中的 `cvOSCcv` 接收端口为 **7001**；
- 检查主音量正常。

---

## 🚀 启动表演（在你的电脑上运行）

在你的电脑上打开一个终端窗口，执行这一行命令：

```bash
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test && ./launch_performance.sh
```

脚本启动后，终端会清晰打印如下指引（示例）：
```text
======================================================================
💻【主机 A（你的电脑：发声 + 模型 + VCV）】
   网页地址 : http://127.0.0.1:8080/ (已自动在浏览器打开)
   操作角色 : 勾选 Participant A
   会话凭据 : Session ID = s_perf_20261003_110000  |  Token = token-A-20261003_110000
----------------------------------------------------------------------
💻【副机 B（另一台电脑：受听参与者）】
   请确保副机与本机连接同一个 Wi-Fi (局域网) 或手机热点！
   在副机浏览器输入 : http://192.168.0.102:8080/
   操作角色 : 勾选 Participant B
   会话凭据 : Session ID = s_perf_20261003_110000  |  Token = token-B-20261003_110000
======================================================================
```

---

## 🎮 双方操作分配

### 电脑 A（你的电脑 / 窗口）：
1. 浏览器已经自动弹开 `http://127.0.0.1:8080/`；
2. 填入终端上显示的 **Session ID**；
3. 勾选 **Participant A**；
4. 填入 **Token A**；
5. 点击 **Connect to Session**，进入后点击 **Mark Ready**。

### 电脑 B（对方电脑）：
1. 在对方电脑的浏览器（Chrome / Safari / Edge 均可，甚至手机/iPad 也可以）打开终端提示的地址（如 `http://192.168.0.102:8080/`）；
2. 填入相同的 **Session ID**；
3. 勾选 **Participant B**；
4. 填入 **Token B**；
5. 点击 **Connect to Session**，进入后点击 **Mark Ready**。

---

## 🎭 现场表演交互轮次（全自动）

双方都点击 **Ready** 之后，任一电脑点击 **Start Session**：

1. **Round 1（A 发声 $\rightarrow$ B 聆听）**：
   - 电脑 A（Sender）：输入你的即时身体感受（Somatic Inscription）并调节 VAD 滑块，点击 **Transmit**；
   - 你的电脑在后台调用 Qwen 并在 1~3 秒内计算出电压，实时驱动 VCV Rack 变声；
   - 电脑 B（Receiver）：静默聆听现场音箱变化，在电脑 B 上记录感受到的身体移位（Somatic Shift），评估 VAD 滑块并提交；
   - 双方屏幕出现投票框，分别点击 **Vote: Continue to Next Round**。

2. **Round 2（B 发声 $\rightarrow$ A 聆听，角色自动对调！）**：
   - 电脑 B 变成 Sender：对方在电脑 B 上输入身体感受并 Transmit；
   - 你的电脑模型再次计算并调制声音；
   - 电脑 A 变成 Receiver：你静听声音，记录身体移位并提交；
   - 双方点击 **Continue**。

3. **Round 3（A 发声 $\rightarrow$ B 聆听 $\rightarrow$ 自动终局）**：
   - A 发声，B 评估提交；
   - 达到第 3 轮上限，两台电脑**瞬间同时自动切入 Final Settlement（终局解密）**！

4. **终局解密（Settlement）**：
   - 两台电脑屏幕上同时展现完整的 **多轮情感流动连线轨迹（青-紫-橙）**、**量化误解距离指标矩阵** 与 **逐轮全透明文本/模型/OSC 电压审计**；
   - 你电脑上的画面可直接外接投影仪向全场观众投屏讲解。

---

## 🛑 结束与换场
- 表演结束，回到你的终端按 **`Ctrl + C`**，服务完全关闭并释放端口；
- 换下一组观众时，再次运行 `./launch_performance.sh`，系统会自动生成新局域网凭据。
