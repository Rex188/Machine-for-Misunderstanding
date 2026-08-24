# Quickstart — A Machine for Misunderstanding

> 5 分钟跑起来。接口契约见 [`README.md`](README.md)，运行记录见 [`运行记录.md`](运行记录.md)。

## 0. 需要什么

- **Python 3**（仅标准库，零依赖）
- **VCV Rack** + `cvOSCcv` 模块（In Port = **7001**）
- **DeepSeek API key**
- **（可选）Max 9** —— 只用它做界面输入和 VAD/seq 显示

## 1. 配 API key

key 从环境变量读，**请求直连 api.deepseek.com，自动绕开本机代理**（任何终端都能跑，不用管 NO_PROXY）：

```bash
export DEEPSEEK_API_KEY=sk-...      # 或 ANTHROPIC_AUTH_TOKEN
```

没有的话会自动读 `~/.claude/settings.json` 的 `env.ANTHROPIC_AUTH_TOKEN` 兜底。

## 2. 起 VCV

打开 VCV patch，确认 `cvOSCcv` 的 **In Port = 7001**（该模块每次编辑后会自动重置为 7001）。

## 3. 起驱动

```bash
cd portfolio/project2/workflow
python3 seq_to_osc.py --watch seq_input.txt
```

看到 `seq_to_osc 就绪 → 127.0.0.1:7001 | ... watch: seq_input.txt` 就对了。

## 4. 喂文本

三种方式，任选：

- **主用（watch）**：往 `seq_input.txt` 追加一行 = 机器解释一段、编进循环：
  ```bash
  echo "我手心冒汗，想站起来走" >> seq_input.txt
  ```
- **Max 界面**：打开 `max_interface.maxpat`，锁定（Cmd+I）。
  - 预制按钮（热 / 凉 / 缩）：锁定态直接点 = 发送；
  - 自定义文本：解锁点 message 框改文字回车，锁回再点它 = 发送。
  - 右侧实时显示 VAD 四值 + 当前步 / 总步数 / 剩余秒。
- **纯命令行**：预置 seq `python3 seq_to_osc.py "我手心冒汗，想站起来走"`，或交互式 stdin（每行一段，空行退出）。

## 5. 验证

- 终端每喂一段出现：`[seq N] 文本 → {'valence':…, 'arousal':…, 'dominance':…, 'confidence':…} | 停留 X.Xs`
- VCV：音高 / 明暗 / 响度随文本变，锚点间平滑滑动
- Max：VAD 四值、当前步、剩余秒实时刷新（10Hz）
- 机器在锚点间**自动循环**，停留秒数随 confidence 变化（越不确定停留越久）；随时追加，新段编进循环。

## 端口表

| 端口 | 方向 | 内容 |
|---|---|---|
| **7100** | Max → Python | `/text` + string（Max 界面发文本） |
| **7200** | Python → Max | `/state` + 7 float @10Hz（VAD、当前步、总步数、剩余秒） |
| **7201** | Python → Max | `/step_text`（预留，当前界面未用） |
| **7001** | Python → VCV | `/vad/valence|arousal|dominance|confidence` |

## 常用参数

```bash
python3 seq_to_osc.py --glide 0.12              # 锚点间滑动速度(0~1)
python3 seq_to_osc.py --dwell-min 3 --dwell-max 18   # 每步停留范围(秒)
python3 seq_to_osc.py --verbose                 # 每次发送都打印(调试)
```

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 终端 `[seq N]` 显示 `{0.5, 0.5, 0.5, 0.0}` | key 没读到或网络失败。看 stderr 的 `llm_to_vad: 请求失败(…)` / `未找到 key` |
| VCV 没声音 | `cvOSCcv` In Port 是否 = 7001；音频设备是否选对 |
| 端口被占 | `lsof -i :7001` / `:7100` / `:7200` |
| 想让每步停留固定秒数 | `--dwell-min 6 --dwell-max 6` |
| 追加没反应 | 确认是**追加**一行（`>>`），不是覆盖（`>`） |

## 已知限制

- **③ 当前解释的文本显示已移除**（2026-08-24 决策）：Max 9 的 `udpreceive` 承载不了中文文本。界面 = 输入 + VAD/seq 显示；输入主用 watch。
- **confidence 不进 VCV**：只在桥侧决定每步停留秒数。
- **6 维未实现**：协议已留槽位，待与老师对齐命名后补。
- 实验数据自动记录在 `seq_log.jsonl`（reveal 的原始材料）。
