# Blind Test 从零开始 Quickstart

项目：**A Machine for Misunderstanding**  
路径：`/Users/rexli/Documents/Rex/portfolio/project2/blind_test`

本指南包含两种模式：

- **普通实验模式**：启动服务、打开两个网页、完成实验。普通使用者只看下面的“普通实验流程”。
- **开发者调试模式**：后面的 curl、SQLite 和故障排查内容。只有出现问题时才查看。

## 普通实验流程（推荐）

正常实验过程中不需要执行 curl、不需要输入 version、不需要打开 SQLite，也不需要手动检查 Marker。

### 1. 准备 VCV Rack

打开 VCV Rack，只保留一个实例，并加载：

```text
/Users/rexli/Documents/Rex/portfolio/project2/workflow/generative template new mvp.vcv
```

确认 `cvOSCcv` 接收 UDP 7001，音量先调低。

### 2. 创建本次实验

打开一个 Terminal，执行：

```zsh
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
printf '%s' '请输入本次测试编号，例如 20261002_03：'
read -r TEST_TAG
```

这里只输入一次新的测试编号，例如 `20261002_03`，按 Enter。然后在同一个 Terminal 粘贴：

```zsh
export DB_FILE="data/manual_test_${TEST_TAG}.db"
export SESSION_ID="s_manual_${TEST_TAG}"
export TOKEN_A="manual-token-A-${TEST_TAG}"
export TOKEN_B="manual-token-B-${TEST_TAG}"
export PARTICIPANT_A="p_${SESSION_ID}_A"
export PARTICIPANT_B="p_${SESSION_ID}_B"

PYTHONPATH=. python -c 'import os; from db import Database; db=Database(os.environ["DB_FILE"]); db.init_db(); print(db.create_session(os.environ["SESSION_ID"], max_rounds=3))'

PYTHONPATH=. python -c 'from pathlib import Path; import os; Path("data/current_test.env").write_text("export DB_FILE=\"%s\"\nexport SESSION_ID=\"%s\"\nexport TOKEN_A=\"%s\"\nexport TOKEN_B=\"%s\"\nexport PARTICIPANT_A=\"%s\"\nexport PARTICIPANT_B=\"%s\"\n" % tuple(os.environ[k] for k in ("DB_FILE", "SESSION_ID", "TOKEN_A", "TOKEN_B", "PARTICIPANT_A", "PARTICIPANT_B")))'

echo "本次实验已创建：$SESSION_ID"
```

看到 `LOBBY` 和本次实验编号后，继续下一步。不要重复使用同一个编号。

### 3. 启动实验服务

打开第二个 Terminal，执行下面整段；这个 Terminal 只保持运行：

```zsh
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
source data/current_test.env
PYTHONPATH=. python -c 'import os; from db import Database; from service import BlindTestService; from real_model import LocalQwenBackend; from real_osc import RealOscTransport; from server import create_server; db=Database(os.environ["DB_FILE"]); db.init_db(); service=BlindTestService(db=db, model_backend=LocalQwenBackend(), osc_transport=RealOscTransport(host="127.0.0.1", port=7001)); server=create_server(host="127.0.0.1", port=7070, service=service, long_poll_timeout=20.0); print("Blind Test API ready: http://127.0.0.1:7070"); server.serve_forever()'
```

### 4. 启动网页

打开第三个 Terminal，执行：

```zsh
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
python -m http.server 8080 --directory web
```

浏览器打开：`http://127.0.0.1:8080/`

### 5. A、B 加入

在第一个 Terminal 执行：

```zsh
source data/current_test.env
echo "SESSION_ID=$SESSION_ID"
echo "TOKEN_A=$TOKEN_A"
echo "TOKEN_B=$TOKEN_B"
```

使用两个独立浏览器标签页或窗口。前端会用 `sessionStorage` 为每个标签页隔离 A/B 身份；不要复制同一个标签页。

A 窗口填写：

```text
Session Identifier：Terminal 打印的 SESSION_ID
Assigned Slot：Participant A
Security Token：Terminal 打印的 TOKEN_A
```

B 窗口填写同一个 `SESSION_ID`，选择 `Participant B`，并填写 `TOKEN_B`。

### 6. 正常实验操作

网页会自动同步状态，不需要手动调用 API：

1. A、B 都点击 `Ready`；
2. 任一方点击 `Start Experiment`；
3. Round 1：A 输入，B 听声音并反馈；
4. 双方都点击 `Continue`；
5. Round 2：B 输入，A 听声音并反馈；
6. 双方都点击 `Continue`；
7. Round 3：A 输入，B 听声音并反馈；
8. 系统自动进入 `Settlement`，查看 Revelation 和 Metrics。

实验结束后，在 API server 和网页 server 所在终端分别按 `Ctrl-C`。不要删除 `data/` 或 `recordings/`。

普通实验流程到此结束。下面的内容只用于开发者调试。

## 0. 终端安排

建议同时使用 4 个终端窗口。每打开一个新的终端，都要重新激活 Conda 环境：

```bash
conda activate blindtest
```

终端分工：

```text
Terminal A：自动化测试、创建数据库和 Session
Terminal B：启动 HTTP server，此终端必须一直保持运行
Terminal C：模拟客户端 A 的 curl 请求
Terminal D：模拟客户端 B 的 curl 请求
```

VCV Rack 是独立的图形程序，不占用上述终端。

每个终端第一次使用时都执行：

```bash
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
```

## 0.1 每次实验前清场

每次开始新的人工测试时，建议执行一次完整清场。目标是：

```text
旧 Blind Test server 已停止
旧 seq_to_osc / llm_sound 进程已停止
7070 没有旧 HTTP server 占用
7001 只由当前 VCV Rack 使用
使用新的数据库文件或新的 session_id
不删除历史实验数据
```

### A. 先停止旧 server

如果旧 server 还在某个终端运行，回到该终端按：

```text
Ctrl + C
```

看到命令行提示符重新出现，说明 server 已停止。

如果找不到原来的终端，在新的 Terminal A 中检查 7070：

```bash
conda activate blindtest
lsof -nP -iTCP:7070 -sTCP:LISTEN
```

如果有输出，先记下 PID，并确认它确实是旧的 Blind Test Python 进程：

```bash
ps -fp <PID>
```

确认后再停止这个精确的 PID：

```bash
kill <PID>
```

然后重新检查：

```bash
lsof -nP -iTCP:7070 -sTCP:LISTEN
```

没有输出才算清理完成。不要使用宽泛的 `killall python` 或 `pkill python`，否则可能误杀其他程序。

### B. 停止旧 OSC 驱动

检查是否有旧工作流进程：

```bash
ps aux | rg 'seq_to_osc|llm_sound_interactive|llm_to_vad|blind_test'
```

如果发现旧的 `seq_to_osc.py` 或 `llm_sound_interactive.py`，记录 PID，确认后停止对应 PID：

```bash
kill <PID>
```

不要停止 VCV Rack 本身。当前测试需要：

```text
VCV Rack：保留一个实例
Blind Test server：只保留当前一个实例
旧 seq/LLM 驱动：全部停止
```

### C. 检查 7001

```bash
lsof -nP -iUDP:7001
```

理想情况是只有 VCV Rack 监听 UDP 7001。

如果看到旧 Python OSC 进程占用 7001，先确认 PID，再停止它。不要为了清理 7001 而停止当前 VCV Rack。

### D. 重新加载 VCV patch

正式测试前，建议关闭旧 patch，再重新打开：

```text
/Users/rexli/Documents/Rex/portfolio/project2/workflow/generative template new mvp.vcv
```

确认：

- `cvOSCcv` 接收端口为 7001；
- 8 个 OSC Path 正确；
- 音量处于较低水平；
- 没有同时打开第二个 VCV 实例。

如果只是临时修改过 patch，不要覆盖原始 patch；可以关闭而不保存，然后重新打开已知正常版本。

### E. 使用新的数据库文件

不需要手动用 `sqlite3` 建数据库，也不要删除旧数据库。Python 的 `db.init_db()` 会自动创建数据库文件和表。

每次新测试只需要输入一次“本次测试编号”。你不需要自己填写数据库文件名、Session ID、参与者 ID 或 Token。

请在 **Terminal A** 中按下面两个动作操作。这样你只需要手动输入一次编号，其他内容全部自动生成。

**动作 1：打开 Terminal A，激活环境，进入目录，然后只粘贴这一行：**

```bash
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
printf '%s' '请输入本次测试编号，例如 20261002_03：'
read -r TEST_TAG
```

看到提示后，只输入一个新的编号，例如 `20261002_03`，然后按 Enter。编号只能使用英文字母、数字、下划线和连字符。等你看到命令提示符重新出现后，再执行动作 2。

**动作 2：在同一个 Terminal A 中完整粘贴下面这段命令：**

```bash
if [ -z "$TEST_TAG" ]; then
  echo "编号不能为空。请重新粘贴这段命令。"
else
  export DB_FILE="data/manual_test_${TEST_TAG}.db"
  export SESSION_ID="s_manual_${TEST_TAG}"
  export TOKEN_A="manual-token-A-${TEST_TAG}"
  export TOKEN_B="manual-token-B-${TEST_TAG}"
  export PARTICIPANT_A="p_${SESSION_ID}_A"
  export PARTICIPANT_B="p_${SESSION_ID}_B"

  PYTHONPATH=. python -c 'import os; from db import Database; db=Database(os.environ["DB_FILE"]); db.init_db(); print(db.create_session(os.environ["SESSION_ID"], max_rounds=3))'

  PYTHONPATH=. python -c 'from pathlib import Path; import os; Path("data/current_test.env").write_text("export DB_FILE=\"%s\"\nexport SESSION_ID=\"%s\"\nexport TOKEN_A=\"%s\"\nexport TOKEN_B=\"%s\"\nexport PARTICIPANT_A=\"%s\"\nexport PARTICIPANT_B=\"%s\"\n" % tuple(os.environ[k] for k in ("DB_FILE", "SESSION_ID", "TOKEN_A", "TOKEN_B", "PARTICIPANT_A", "PARTICIPANT_B")))'

  echo
  echo "本次测试已创建："
  echo "数据库文件：$DB_FILE"
  echo "Session ID：$SESSION_ID"
  echo "配置文件：data/current_test.env"
  echo "后续打开的新终端，只需要执行：source data/current_test.env"
fi
```

预期结果：你会看到 `status` 为 `LOBBY`，并看到本次生成的数据库文件、Session ID 和 `data/current_test.env`。这一步已经自动完成数据库和 Session 的创建，不需要再手动建任何文件。

检查方法：执行 `cat data/current_test.env` 时，应该看到 6 行 `export ...`，每个变量单独占一行。如果你看到所有内容挤在一行，或者看到字面量 `\\n`，这是旧版初始化文件，直接重新执行动作 1 和动作 2，并输入一个新的测试编号。

重要：`data/current_test.env` 是本次测试的“唯一配置单”。它把同一次测试需要用到的数据库、Session、A/B Token 和参与者 ID 固定下来。后面每打开一个新终端，都先执行：

```bash
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
source data/current_test.env
```

如果继续使用同一个数据库文件，必须回到 Terminal A 重新输入一个全新的测试编号，生成全新的 Session；不要复用已经进入 `ERROR`、`SETTLEMENT` 或 `ABORTED` 的 Session。


## 1. 先不要使用旧工作流

以下文件属于旧的单人/seq 工作流，不是当前 Blind Test 服务：

- `project2/workflow/seq_to_osc.py`
- `project2/workflow/llm_sound_interactive.py`
- `project2/workflow/QUICKSTART.zh-CN.md`

本指南只使用 `project2/blind_test/` 中的代码。

## 2. 建立 Python 环境

在 Terminal A 中执行。建议使用独立 Conda 环境，不要使用系统 Python 3.9：

```bash
conda create -n blindtest python=3.11 -y
conda activate blindtest
which python
python --version
```

后续所有终端统一使用该环境里的 `python`，不要混用系统 `python3`。

预期输出类似：

```text
/.../envs/blindtest/bin/python
Python 3.11.x
```

安装本地 Qwen 依赖：

```bash
python -m pip install torch transformers peft accelerate
```

检查依赖：

```bash
python -c 'import torch; print("torch:", torch.__version__)'
python -c 'import transformers; print("transformers:", transformers.__version__)'
python -c 'import peft; print("peft:", peft.__version__)'
```

预期是三条版本信息，不能出现 `ModuleNotFoundError`。

## 3. 准备 Qwen 模型

LoRA 目录不是完整模型。还需要 Qwen2.5-1.5B-Instruct 基座模型。

LoRA 目录：

```text
/Users/rexli/Documents/Rex/portfolio/project2/models/qwen_lora
```

如果基座模型已经在本地，才设置 `BASE_MODEL`，并且必须替换成真实存在的绝对路径：

```bash
export BASE_MODEL=/absolute/path/to/Qwen2.5-1.5B-Instruct
```

上面的 `/absolute/path/to/...` 只是示例，不能原样执行。如果没有确定的本地路径，请不要设置 `BASE_MODEL`。

如果模型已经通过 Hugging Face 下载过，直接取消自定义路径，让程序使用默认模型名和本地缓存：

```bash
unset BASE_MODEL
```

如果本地没有缓存，第一次运行可能下载约 3GB。首次下载和加载会比较慢，后续推理会快很多。

## 4. 运行自动回归测试

在 Terminal A 中执行。先不要打开 VCV Rack，因为 `test_real_osc.py` 会使用 UDP 7001 做 loopback 测试。

```bash
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
PYTHONPATH=. python test_db.py
PYTHONPATH=. python test_state_machine.py
PYTHONPATH=. python test_metrics.py
PYTHONPATH=. python test_acoustic_bridge.py
PYTHONPATH=. python test_service.py
PYTHONPATH=. python test_server.py
PYTHONPATH=. python test_real_osc.py
PYTHONPATH=. python test_real_model.py
```

预期每个测试都出现类似：

```text
[ALL TESTS PASSED]
```

最后不能有 `Traceback` 或 `FAILED`。

## 5. 单独测试真实 Qwen

仍然在 Terminal A 中执行。不要新开终端；如果新开了，必须重新执行 `conda activate blindtest`，并重新确认 `BASE_MODEL` 设置。

```bash
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
PYTHONPATH=. python -c 'from real_model import LocalQwenBackend; print(LocalQwenBackend().infer("My chest feels compressed and my breathing becomes shallow.").to_dict())'
```

必须看到：

```text
status = SUCCESS
backend = local_qwen
model_name = Qwen/Qwen2.5-1.5B-Instruct+LoRA
```

实际输出是一个 Python dictionary，预期包含：

```text
'status': 'SUCCESS'
'fallback_used': False
'output': {
    'valence': 数字,
    'arousal': 数字,
    'dominance': 数字,
    'confidence': 数字
}
```

第一次运行的 `latency_ms` 可能很高，因为包含模型加载；第二次通常会明显变快。

## 6. 打开 VCV Rack

这一步不需要终端。在 macOS 中打开 VCV Rack：

打开：

```text
/Users/rexli/Documents/Rex/portfolio/project2/workflow/generative template new mvp.vcv
```

在 `cvOSCcv` 中确认：

- 接收端口是 `7001`；
- CH 1–8 已经接到实际声音模块；
- 音频输出设备正确；
- 总音量先调低；
- 不要同时启动旧的 `seq_to_osc.py`。

八个 OSC Path 必须是：

```text
/param/timbre
/param/frequency
/param/amplitude
/param/envelope
/param/mode
/param/chord
/param/type
/param/noise
```

检查 UDP 端口：

```bash
lsof -nP -iUDP:7001
```

如果 VCV 正在监听，应该能看到 VCV Rack 相关进程。若没有输出，先回到 VCV 检查 `cvOSCcv` 的接收端口。

## 7. 创建测试数据库和 Session

保持 VCV 开启。第 0.1 节已经在 Terminal A 中自动完成这一步。你可以用下面两行确认当前测试配置：

```bash
echo "$DB_FILE"
echo "$SESSION_ID"
```

如果没有输出，请不要自己猜文件名；回到 Terminal A，重新执行第 0.1 节的完整初始化命令。

第 0.1 节完成后，数据库和 Session 已经创建。预期状态是：

```text
LOBBY
```

本次测试的数据库文件和 Session ID 以 Terminal A 中打印的内容为准。后面不要手动重写它们；新终端统一使用 `source data/current_test.env`。

## 8. 启动 HTTP 服务

打开 Terminal B，重新激活环境并进入目录。新终端不会自动继承 Terminal A 的变量，所以加载第 0.1 节自动生成的配置文件：

```bash
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
source data/current_test.env
echo "使用数据库：$DB_FILE"
echo "使用 Session：$SESSION_ID"
```

当前 `server.py` 是服务工厂，不是直接可执行脚本。使用以下命令启动：

```bash
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
PYTHONPATH=. python -c 'import os; from db import Database; from service import BlindTestService; from real_model import LocalQwenBackend; from real_osc import RealOscTransport; from server import create_server; db=Database(os.environ["DB_FILE"]); db.init_db(); service=BlindTestService(db=db, model_backend=LocalQwenBackend(), osc_transport=RealOscTransport(host="127.0.0.1", port=7001)); server=create_server(host="127.0.0.1", port=7070, service=service, long_poll_timeout=20.0); print("Blind Test server: http://127.0.0.1:7070"); print("Database:", os.environ["DB_FILE"]); print("Session:", os.environ["SESSION_ID"]); server.serve_forever()'
```

看到以下两行后，说明 server 已启动：

```text
Blind Test server: http://127.0.0.1:7070
Database: data/manual_test_<本次测试编号>.db
Session: s_manual_<本次测试编号>
```

Terminal B 必须保持运行。不要在这个终端继续输入其他命令。

打开 Terminal C，重新激活环境，然后检查：

```bash
curl -i http://127.0.0.1:7070/api/blind/health
```

预期 HTTP 200，并返回 `status: ok`。

## 8.1 使用 Phase 6 浏览器前端

Phase 6 前端位于：

```text
/Users/rexli/Documents/Rex/portfolio/project2/blind_test/web/
```

当前 `server.py` 只提供 API，不直接提供 `web/index.html`。因此需要另开 **Terminal E** 启动一个本地静态文件服务。

在 Terminal E 执行：

```zsh
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
python -m http.server 8080 --directory web
```

看到类似下面的输出后，Terminal E 保持运行：

```text
Serving HTTP on 0.0.0.0 port 8080
```

打开浏览器访问：

```text
http://127.0.0.1:8080/
```

A 和 B 应使用两个独立的浏览器标签页或窗口。前端会用 `sessionStorage` 隔离两个参与者的身份；不要复制同一个标签页。

在 Terminal A 中打印本次测试需要填写到浏览器的真实值：

```zsh
echo "SESSION_ID=$SESSION_ID"
echo "TOKEN_A=$TOKEN_A"
echo "TOKEN_B=$TOKEN_B"
```

下面的 `$SESSION_ID`、`$TOKEN_A`、`$TOKEN_B` 只是变量名称，不要把美元符号和变量名原样填入浏览器；请复制 Terminal A 实际打印出来的值。

### 浏览器窗口 A

在 Join 页面填写：

```text
Session Identifier:   $SESSION_ID
Assigned Slot:        Participant A
Security Token:       $TOKEN_A
```

点击 `Connect to Session`。

### 浏览器窗口 B

在第二个独立窗口填写：

```text
Session Identifier:   $SESSION_ID
Assigned Slot:        Participant B
Security Token:       $TOKEN_B
```

点击 `Connect to Session`。

### 浏览器前端验收顺序

1. A、B 都成功 Join 后，两边都点击 `Ready`。
2. 一方点击 `Start Experiment`，确认 Round 1 显示：A = Sender，B = Receiver。
3. Round 1：A 输入文本和 VAD，B 听声音并提交反馈。
4. Round 1 完成后，A、B 都点击 `Continue`。
5. Round 2 检查：B = Sender，A = Receiver。
6. Round 2 完成后，A、B 都点击 `Continue`。
7. Round 3 检查：A = Sender，B = Receiver。
8. Round 3 完成后，状态自动进入 `SETTLEMENT`，显示 Revelation、轨迹和 Metrics。

每一轮都要观察：

- 顶部 `ROUND` 是否正确；
- `ROLE` 是否正确；
- `STATE` 是否正确；
- `version` 是否持续更新；
- Marker 提交后是否显示已同步；
- VCV 声音是否更新并持续播放；
- Receiver 是否看不到 Sender 文本、Sender VAD 和模型数据。

### 刷新恢复测试

在任意非终局状态刷新页面。预期：

- 页面从 sessionStorage 恢复当前参与者身份；
- 不要求重新 Join；
- 自动继续请求后端 state；
- Round、Role、State 和 version 恢复正确。

如果需要清除当前浏览器身份，使用页面右上角的 `Reset`，然后重新填写 Join 信息。不要在实验中途点击 `Reset`。

### 前端代码快速检查

如果修改过前端文件，在项目目录执行：

```zsh
node -c web/coords.js
node -c web/revelation.js
node -c web/app.js
```

三个命令都没有输出错误，才继续浏览器测试。

### 关闭前端

人工测试完成后，在 Terminal E 按：

```text
Ctrl-C
```

API server 仍在运行时，Terminal E 可以重新启动前端静态服务；不需要重新创建数据库或 Session。

如果只想使用 curl 做底层 API 验证，可以继续执行下面第 9 节开始的命令。浏览器前端测试不需要同时重复执行 curl 流程。

## 9. A 和 B 加入

下面开始，Terminal C 模拟 A，Terminal D 模拟 B。两个终端都要先执行：

```bash
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
source data/current_test.env
```

不要再填写 `TEST_TAG`，也不要手动修改 Session ID。`source data/current_test.env` 已经自动加载本次测试的全部编号。

### A

在 Terminal C 执行：

```bash
python -c 'import json, os; print(json.dumps({"session_id": os.environ["SESSION_ID"], "label": "A", "client_token": os.environ["TOKEN_A"]}))' | curl -s -X POST http://127.0.0.1:7070/api/blind/join -H 'Content-Type: application/json' --data-binary @- | python -m json.tool
```

### B

在 Terminal D 执行：

```bash
python -c 'import json, os; print(json.dumps({"session_id": os.environ["SESSION_ID"], "label": "B", "client_token": os.environ["TOKEN_B"]}))' | curl -s -X POST http://127.0.0.1:7070/api/blind/join -H 'Content-Type: application/json' --data-binary @- | python -m json.tool
```

参与者 ID 应为：

```text
$PARTICIPANT_A
$PARTICIPANT_B
```

如果返回 `JOIN_REJECTED`，先检查这个 session 是否已经加入过 A/B；不要反复使用同一个 session 做新测试。

## 10. A 和 B Ready

A 在 Terminal C 执行，B 在 Terminal D 执行。两个请求都成功后，session 应从 `LOBBY` 进入 `READY`。

```bash
curl -s -X POST http://127.0.0.1:7070/api/blind/ready -H 'Content-Type: application/json' -H "X-Session-Token: $TOKEN_A" -d "{\"session_id\":\"$SESSION_ID\",\"participant_id\":\"$PARTICIPANT_A\"}" | python -m json.tool
```

```bash
curl -s -X POST http://127.0.0.1:7070/api/blind/ready -H 'Content-Type: application/json' -H "X-Session-Token: $TOKEN_B" -d "{\"session_id\":\"$SESSION_ID\",\"participant_id\":\"$PARTICIPANT_B\"}" | python -m json.tool
```

## 11. 启动实验

在 Terminal C 执行：

```bash
curl -s -X POST http://127.0.0.1:7070/api/blind/start -H 'Content-Type: application/json' -H "X-Session-Token: $TOKEN_A" -d "{\"session_id\":\"$SESSION_ID\",\"participant_id\":\"$PARTICIPANT_A\"}" | python -m json.tool
```

成功后：

```text
状态：INPUT_OPEN
A：Sender
B：Receiver
```

如果返回 `STALE_VERSION`，不要重试同一个旧请求，先重新查询当前状态和 `version`。

## 12. 每次提交前读取最新版本

在对应客户端的终端中执行。A 的请求在 Terminal C，B 的请求在 Terminal D。

不要把 `client_version` 固定写成 3 或 5。每次操作前执行：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_A" -H "X-Session-Token: $TOKEN_A" | python -m json.tool
```

记录返回中的 `version`、`status`、`round_index` 和 `role`。

预期示例：

```text
version: 5
status: INPUT_OPEN
role: SENDER
round_index: 0
```

## 13. Round 1：A 输入

在 Terminal C 执行。把上一步读取到的最新版本填入 `<A当前version>`。

```bash
curl -s -X POST http://127.0.0.1:7070/api/blind/submit_input \
  -H 'Content-Type: application/json' \
  -H "X-Session-Token: $TOKEN_A" \
  --data-binary @- <<JSON | python -m json.tool
{
    "session_id": "$SESSION_ID",
    "participant_id": "$PARTICIPANT_A",
    "client_version": <A当前version>,
    "idempotency_key": "manual-r1-input-a-02",
    "payload": {
      "text": "My chest feels compressed and my breathing becomes shallow.",
      "input_vadc": {
        "valence": 0.2,
        "arousal": 0.8,
        "dominance": 0.1,
        "confidence": 0.7
      },
      "client_submission_id": "manual-r1-input-a-02"
    }
}
JSON
```

成功条件：

- `accepted: true`；
- 返回 `marker_id`；
- 返回 `sequence: 1`；
- VCV 声音发生变化；
- 状态进入 `RECEIVER_RESPONSE`。

如果返回 `Model inference failed`，检查 Terminal B 的 server 输出，并确认真实 Qwen smoke test 是否返回 `status: SUCCESS`。

## 14. 检查 B 的双盲投影

在 Terminal D 执行：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_B" -H "X-Session-Token: $TOKEN_B" | python -m json.tool
```

B 不应该看到：

- A 的原文；
- A 的 input VAD；
- model VAD；
- model reasoning；
- raw model output。

## 15. Round 1：B 提交反馈

先在 Terminal D 查询 B 的最新 `version`，再提交：

```bash
curl -s -X POST http://127.0.0.1:7070/api/blind/submit_receiver \
  -H 'Content-Type: application/json' \
  -H "X-Session-Token: $TOKEN_B" \
  --data-binary @- <<JSON | python -m json.tool
{
    "session_id": "$SESSION_ID",
    "participant_id": "$PARTICIPANT_B",
    "client_version": <B当前version>,
    "idempotency_key": "manual-r1-response-b-02",
    "payload": {
      "receiver_vadc": {
        "valence": 0.4,
        "arousal": 0.6,
        "dominance": 0.3,
        "confidence": 0.5
      },
      "somatic_shift": "The sound made my chest feel more open but less stable.",
      "listening_confirmed": true
    }
}
JSON
```

完成后应有：1 个 marker、1 个 receiver response、1 个 metrics。

在 Terminal D 再检查一次 B 的状态：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_B" -H "X-Session-Token: $TOKEN_B" | python -m json.tool
```

预期：`status=ROUND_COMPLETE`、`round_index=0`、`role=RECEIVER`。确认无误后，才执行下面两次 `continue`。

## 16. 进入下一轮

第一轮完成后，双方都要执行 `continue`。这一步只表示“我愿意进入下一轮”，必须 A、B 都成功后才会开启第二轮。

### B 继续

```bash
python -c 'import json, os; print(json.dumps({"session_id": os.environ["SESSION_ID"], "participant_id": os.environ["PARTICIPANT_B"]}))' | curl -s -X POST http://127.0.0.1:7070/api/blind/continue -H 'Content-Type: application/json' -H "X-Session-Token: $TOKEN_B" --data-binary @- | python -m json.tool
```

### A 继续

```bash
python -c 'import json, os; print(json.dumps({"session_id": os.environ["SESSION_ID"], "participant_id": os.environ["PARTICIPANT_A"]}))' | curl -s -X POST http://127.0.0.1:7070/api/blind/continue -H 'Content-Type: application/json' -H "X-Session-Token: $TOKEN_A" --data-binary @- | python -m json.tool
```

第二轮角色应变为：

```text
B：Sender
A：Receiver
```

两次 `continue` 都成功后，必须分别检查 A 和 B：

在 Terminal C 执行：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_A" -H "X-Session-Token: $TOKEN_A" | python -m json.tool
```

预期：`status` 为 `INPUT_OPEN`，`round_index` 为 `1`，`role` 为 `RECEIVER`。

在 Terminal D 执行：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_B" -H "X-Session-Token: $TOKEN_B" | python -m json.tool
```

预期：`status` 为 `INPUT_OPEN`，`round_index` 为 `1`，`role` 为 `SENDER`。

注意：`<A当前version>`、`<B当前version>` 不是要原样输入的代码，也不是环境变量。它们表示你刚刚用 `/state` 查询到的实际数字，例如 `12`。每一次操作都必须重新查询当前数字。

### 第二轮：B 输入，A 反馈

先在 Terminal D 查询 B 的状态：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_B" -H "X-Session-Token: $TOKEN_B" | python -m json.tool
```

确认 B 的 `role` 是 `SENDER`，记下返回的 `version`，替换下面的 `<B第二轮version>`：

```bash
curl -s -X POST http://127.0.0.1:7070/api/blind/submit_input \
  -H 'Content-Type: application/json' \
  -H "X-Session-Token: $TOKEN_B" \
  --data-binary @- <<JSON | python -m json.tool
{
  "session_id": "$SESSION_ID",
  "participant_id": "$PARTICIPANT_B",
  "client_version": <B第二轮version>,
  "idempotency_key": "manual-r2-input-b",
  "payload": {
    "text": "The sound leaves a wider space around my breath.",
    "input_vadc": {
      "valence": 0.6,
      "arousal": 0.5,
      "dominance": 0.4,
      "confidence": 0.7
    },
    "client_submission_id": "manual-r2-input-b"
  }
}
JSON
```

然后在 Terminal C 查询 A 的状态，确认 A 的 `role` 是 `RECEIVER`，记下新的 `version`：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_A" -H "X-Session-Token: $TOKEN_A" | python -m json.tool
```

把返回的数字替换到 `<A第二轮version>` 后，在 Terminal C 提交反馈：

```bash
curl -s -X POST http://127.0.0.1:7070/api/blind/submit_receiver \
  -H 'Content-Type: application/json' \
  -H "X-Session-Token: $TOKEN_A" \
  --data-binary @- <<JSON | python -m json.tool
{
  "session_id": "$SESSION_ID",
  "participant_id": "$PARTICIPANT_A",
  "client_version": <A第二轮version>,
  "idempotency_key": "manual-r2-response-a",
  "payload": {
    "receiver_vadc": {
      "valence": 0.5,
      "arousal": 0.5,
      "dominance": 0.4,
      "confidence": 0.7
    },
    "somatic_shift": "The sound changes the space around my breathing.",
    "listening_confirmed": true
  }
}
JSON
```

第二轮反馈成功后，执行下面两条命令，不能跳过。

在 Terminal C 让 A 继续：

```bash
python -c 'import json, os; print(json.dumps({"session_id": os.environ["SESSION_ID"], "participant_id": os.environ["PARTICIPANT_A"]}))' | curl -s -X POST http://127.0.0.1:7070/api/blind/continue -H 'Content-Type: application/json' -H "X-Session-Token: $TOKEN_A" --data-binary @- | python -m json.tool
```

在 Terminal D 让 B 继续：

```bash
python -c 'import json, os; print(json.dumps({"session_id": os.environ["SESSION_ID"], "participant_id": os.environ["PARTICIPANT_B"]}))' | curl -s -X POST http://127.0.0.1:7070/api/blind/continue -H 'Content-Type: application/json' -H "X-Session-Token: $TOKEN_B" --data-binary @- | python -m json.tool
```

不要复用第一轮或第二轮的 `idempotency_key`。

然后检查第三轮是否真的打开。

在 Terminal C 执行：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_A" -H "X-Session-Token: $TOKEN_A" | python -m json.tool
```

预期：`status` 为 `INPUT_OPEN`，`round_index` 为 `2`，`role` 为 `SENDER`。

在 Terminal D 执行：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_B" -H "X-Session-Token: $TOKEN_B" | python -m json.tool
```

预期：`status` 为 `INPUT_OPEN`，`round_index` 为 `2`，`role` 为 `RECEIVER`。

### 第三轮：A 输入，B 反馈

第三轮角色会切回：

```text
A：Sender
B：Receiver
```

#### 第三轮第 1 步：A 先检查状态

在 Terminal C 执行：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_A" -H "X-Session-Token: $TOKEN_A" | python -m json.tool
```

必须确认：`status=INPUT_OPEN`、`round_index=2`、`role=SENDER`。记下返回的 `version`，把它替换到下面的 `<A第三轮version>`，不能原样输入尖括号。

#### 第三轮第 2 步：A 提交输入

仍在 Terminal C 执行：

```bash
curl -s -X POST http://127.0.0.1:7070/api/blind/submit_input \
  -H 'Content-Type: application/json' \
  -H "X-Session-Token: $TOKEN_A" \
  --data-binary @- <<JSON | python -m json.tool
{
  "session_id": "$SESSION_ID",
  "participant_id": "$PARTICIPANT_A",
  "client_version": <A第三轮version>,
  "idempotency_key": "manual-r3-input-a",
  "payload": {
    "text": "I notice the sound moving between tension and release.",
    "input_vadc": {
      "valence": 0.5,
      "arousal": 0.6,
      "dominance": 0.5,
      "confidence": 0.7
    },
    "client_submission_id": "manual-r3-input-a"
  }
}
JSON
```

预期：返回 `accepted: true`、新的 `marker_id`、`sequence: 3`，状态变为 `RECEIVER_RESPONSE`，并且 VCV 声音发生变化。

#### 第三轮第 3 步：B 检查双盲状态

在 Terminal D 执行：

```bash
curl -s "http://127.0.0.1:7070/api/blind/state?session_id=$SESSION_ID&participant_id=$PARTICIPANT_B" -H "X-Session-Token: $TOKEN_B" | python -m json.tool
```

必须确认：`status=RECEIVER_RESPONSE`、`round_index=2`、`role=RECEIVER`。B 不应看到 A 的原文、A 的 VAD 或模型 VAD。记下返回的 `version`，把它替换到下面的 `<B第三轮version>`。

#### 第三轮第 4 步：B 提交反馈

仍在 Terminal D 执行：

```bash
curl -s -X POST http://127.0.0.1:7070/api/blind/submit_receiver \
  -H 'Content-Type: application/json' \
  -H "X-Session-Token: $TOKEN_B" \
  --data-binary @- <<JSON | python -m json.tool
{
  "session_id": "$SESSION_ID",
  "participant_id": "$PARTICIPANT_B",
  "client_version": <B第三轮version>,
  "idempotency_key": "manual-r3-response-b",
  "payload": {
    "receiver_vadc": {
      "valence": 0.5,
      "arousal": 0.5,
      "dominance": 0.5,
      "confidence": 0.7
    },
    "somatic_shift": "The final sound leaves a mixed sense of tension and release.",
    "listening_confirmed": true
  }
}
JSON
```

预期：返回 `status=SETTLEMENT`、`current_round_index=2`，第三轮完成。此时不需要再执行 `continue`。

## 17. 查询完整 Summary

第三轮完成后，或者任一方提前结束后，状态应为 `SETTLEMENT` 或 `ABORTED`。然后在 Terminal C 查询：

```bash
curl -s "http://127.0.0.1:7070/api/blind/summary?session_id=$SESSION_ID&participant_id=$PARTICIPANT_A" -H "X-Session-Token: $TOKEN_A" | python -m json.tool
```

## 18. 检查 SQLite 数据

在 Terminal A 或新开的 Terminal E 中执行。新终端必须先激活环境、进入项目目录，并加载本次测试配置。不要直接猜数据库文件名。

```bash
conda activate blindtest
cd /Users/rexli/Documents/Rex/portfolio/project2/blind_test
source data/current_test.env
echo "即将检查：$DB_FILE"
ls -lh "$DB_FILE"
sqlite3 "$DB_FILE"
```

如果 `ls -lh "$DB_FILE"` 报 `No such file or directory`，先不要输入任何 SQL。这说明当前终端没有加载正确配置，退出 sqlite3，重新执行上面的 `source data/current_test.env`。不要继续查询，否则 SQLite 可能自动创建一个空数据库。

执行：

```sql
.headers on
.mode column
.tables

SELECT session_id, status, current_round_index, version FROM sessions;
SELECT round_index, sender_id, receiver_id, status, marker_id FROM rounds ORDER BY round_index;
SELECT sequence, round_id, status, created_at FROM markers ORDER BY sequence;
SELECT event_type, from_state, to_state, created_at FROM state_events ORDER BY created_at;
SELECT round_id, metrics_id, raw_distance_json, inter_round_drift FROM metrics ORDER BY rowid;
```

三轮完整测试应看到：

```text
rounds = 3
markers = 3
receiver_responses = 3
metrics = 3
marker sequence = 1, 2, 3
```

如果只测试一轮，则相应地应看到 1 个 marker、1 个 receiver response 和 1 个 metrics。

## 19. 常见问题

### `Expecting value: line 1 column 1`

说明 curl 没有返回 JSON。去掉 `-s`：

```bash
curl -i http://127.0.0.1:7070/api/blind/health
```

### `Can't assign requested address`

不要使用 `127.0.0.0`。本机测试使用 `127.0.0.1`，局域网测试使用 `0.0.0.0`。

### `STALE_VERSION`

说明使用了旧版本号。重新查询 `/api/blind/state`，使用最新 `version`。

### `Model inference failed`

先运行真实 Qwen smoke test，检查 torch、transformers、peft 和基座模型是否存在。

### A 提交成功但 VCV 没有变化

依次检查：

1. 返回是否为 `accepted: true`；
2. SQLite 是否有 marker；
3. marker 的 `osc_dispatch.status` 是否为 `SENT`；
4. `cvOSCcv` 接收端口是否是 7001；
5. OSC Path 是否是 `/param/...`；
6. CH 1–8 是否接入实际模块；
7. 是否同时运行了旧 `seq_to_osc.py`。

### `test_real_model.py` 报没有 torch

确认：

```bash
conda activate blindtest
which python
```

然后检查并安装模型依赖。

## 20. 人工验收停止条件

出现以下任意情况，应停止测试：

- VCV 没有声音；
- 声音爆音或削波；
- OSC 地址和 patch 不对应；
- marker 没有创建；
- 一个输入创建多个 marker；
- Receiver 看到了 Sender 私密数据；
- 角色没有正确交换；
- 刷新后状态错乱；
- 出现第四轮；
- marker 时间顺序异常；
- 模型失败却创建了 marker。
