# Blind Test 实现日志

项目：**A Machine for Misunderstanding**  
路径：`project2/blind_test/`  
最后更新：**2026-10-02**

## 项目方向

这个系统把交流理解为一连串的解释过程，而不是文本的直接传输。

目前已经确定的核心原则：

- 服务器是 session 状态的唯一权威来源；
- marker 是声音状态变化的唯一时间锚点；
- VCV Rack 持续发声，不使用固定 15 秒播放窗口；
- Settlement 之前，Receiver 不得看到 Sender 的私密数据；
- 录屏是外部 artifact，不参与状态机；
- 音频文件不是实验运行的必要条件。

## Phase 1 — SQLite 标准数据层

状态：**已完成并通过测试**  
Commit：`d321c83 feat(blind_test): complete Phase 1 canonical SQLite data layer with tests`

已实现文件：`schema.sql`、`db.py`、`test_db.py`。

数据库包含 10 张实体表：

- `sessions`：实验会话；
- `participants`：参与者；
- `rounds`：实验轮次；
- `input_events`：Sender 输入事件；
- `model_runs`：模型调用记录；
- `markers`：声音状态变化的时间标记；
- `receiver_responses`：Receiver 反馈；
- `metrics`：量化指标；
- `state_events`：状态变化审计；
- `artifacts`：录屏等外部文件引用。

已验证：

- SQLite 外键约束已开启；
- WAL 日志模式已开启；
- busy timeout 设置为 5 秒；
- 每个线程使用独立 SQLite 连接；
- 不跨线程共享 connection；
- 已建立外键约束和性能索引；
- `client_submission_id` 可以防止请求重放；
- 可以完整导出全部 10 张表的数据。

数据层包含两类数据库原子提交：

1. Sender 输入、模型记录、marker、轮次状态和状态事件的提交；
2. Receiver 反馈、metrics、轮次完成和状态事件的提交。

模型调用和 OSC 网络调用均在 SQLite transaction 外部执行。

## Phase 2 — 权威状态机

状态：**已完成并通过测试**  
Commit：`348a8b0 feat(blind_test): complete Phase 2 pure authoritative state machine with exhaustive tests`

已实现文件：`state_machine.py`、`test_state_machine.py`。同时在 `schema.sql` 和 `db.py` 中加入了双方继续意向的持久化字段。

系统包含 11 种状态：

- `LOBBY`：等待参与者；
- `READY`：双方准备完成；
- `INPUT_OPEN`：等待当前 Sender 输入；
- `MODEL_PROCESSING`：模型推理中；
- `SOUND_UPDATE`：更新声音状态；
- `RECEIVER_RESPONSE`：等待 Receiver 反馈；
- `ROUND_COMPLETE`：本轮完成；
- `NEXT_ROUND_PENDING`：等待双方决定是否继续；
- `SETTLEMENT`：结算揭晓；
- `ERROR`：可恢复错误；
- `ABORTED`：不可恢复终止。

已验证：

- 状态机不依赖数据库、HTTP、LLM、OSC、VCV 或前端；
- 所有状态变化通过显式事件触发；
- 角色会在轮次之间自动交换；
- 最多进行 3 轮；
- 严格校验 Sender 和 Receiver 权限；
- 拒绝陈旧的 `round_id` 和 `client_version`；
- 重复请求具备幂等性；
- `SETTLEMENT` 和 `ABORTED` 进入终态后不可继续操作；
- 模型失败和声学更新失败可以进入错误恢复流程。

## Phase 3 — 应用编排器与确定性指标

状态：**已完成并通过测试**  
Commit：**尚未提交，修改保持未 commit 状态**

已实现文件：`metrics.py`、`acoustic_bridge.py`、`service.py`、`test_metrics.py`、`test_acoustic_bridge.py`、`test_service.py`。

指标引擎是纯函数模块，已经支持：

- 只接受 `[0, 1]` 范围内的有限 VADC 数值；
- 拒绝缺失字段；
- 拒绝 NaN 和 Infinity；
- 支持零向量；
- 保存 raw model distance；
- 保存 raw medium distance；
- 保存 raw total distance；
- 单独保存 confidence-adjusted distance；
- 第一轮的 `inter_round_drift` 返回 `null`。

单位 VAD 立方体的最大欧氏距离使用 `sqrt(3)` 归一化。

声学桥接层定义了：

- `ModelBackend`；
- `OscTransport`；
- `FakeModelBackend`；
- `FakeOscTransport`。

目前冻结了 8 个 OSC 通道：

- `/param/timbre`；
- `/param/frequency`；
- `/param/amplitude`；
- `/param/envelope`；
- `/param/mode`；
- `/param/chord`；
- `/param/type`；
- `/param/noise`。

`service.py` 负责协调数据库、状态机、指标、模型后端、OSC 传输和隐私投影。

已验证：

- 三轮完整流程可以运行；
- 每次成功输入只产生一个 committed marker；
- 模型失败不会创建 marker；
- OSC 失败不会创建 marker；
- 重复 `idempotency_key` 返回原始结果；
- Settlement 前 Receiver 看不到 Sender 文本、Sender VAD、模型 VAD 或模型推理过程。

## Phase 4 — HTTP API 集成

状态：**已完成并通过测试**  
Commit：**尚未提交，修改保持未 commit 状态**

已实现文件：`server.py`、`test_server.py`。

HTTP 网关使用标准库 `ThreadingHTTPServer`，并具备：

- 线程隔离的 SQLite 连接；
- `X-Session-Token` 身份验证；
- 统一 JSON 错误格式；
- 不向客户端暴露 Python traceback；
- 按参与者返回不同隐私投影；
- 基于 session version 的长轮询；
- 不在 HTTP handler 中实现状态机和 SQL 业务逻辑。

已实现接口：

- `GET /api/blind/health`；
- `POST /api/blind/join`；
- `POST /api/blind/ready`；
- `POST /api/blind/start`；
- `GET /api/blind/state`；
- `POST /api/blind/submit_input`；
- `POST /api/blind/submit_receiver`；
- `POST /api/blind/continue`；
- `POST /api/blind/end`；
- `GET /api/blind/summary`。

已验证：

- 双客户端加入；
- 第三个参与者被拒绝；
- 错误 token 被拒绝；
- Sender/Receiver 角色权限正确；
- 旧版本请求被拒绝；
- 重复请求具备幂等性；
- 并发输入只产生一个 marker；
- 长轮询可以超时和被事件唤醒；
- 畸形 JSON 会安全返回错误；
- 响应中不泄露 traceback；
- Receiver 隐私投影测试通过。

## Phase 5A — 真实 UDP/OSC 传输

状态：**已完成并通过测试**  
Commit：**尚未提交，修改保持未 commit 状态**

已实现文件：`real_osc.py`、`test_real_osc.py`。

实现内容：

- 使用标准库实现 OSC 1.0 编码；
- 字符串按 4 字节对齐；
- 使用大端 32 位浮点数；
- 支持 `OSC_HOST`、`OSC_PORT`、`OSC_TIMEOUT`；
- 默认目标为 `127.0.0.1:7001`；
- 严格验证 8 个电压通道；
- 明确返回网络失败状态；
- 不依赖第三方 OSC 包；
- 兼容原有 `OscTransport` 接口。

测试覆盖：

- OSC 数据包编码；
- 电压边界；
- 缺失值、非法值、NaN、Infinity；
- 本地 UDP loopback；
- 恰好 8 个 OSC 数据包；
- 与 service 的集成。

## Phase 5B — 本地真实模型后端

状态：**已完成并通过测试**  
Commit：**尚未提交，修改保持未 commit 状态**

已实现文件：`real_model.py`、`test_real_model.py`。

实现内容：

- 本地 Qwen2.5-1.5B 推理；
- 自动加载 `models/qwen_lora/` 中的 LoRA 权重；
- 支持 Apple Silicon MPS、CUDA 和 CPU；
- 不调用外部网络；
- 不硬编码 API key；
- 保存 prompt version；
- 保存模型原始输出；
- 保存推理耗时。

模型输出严格验证：

- 非法 JSON 会被拒绝；
- 缺少字段会被拒绝；
- 超出 `[0, 1]` 的值会被拒绝；
- NaN 和 Infinity 会被拒绝；
- 不会静默回落到中性向量；
- 模型失败不会产生 committed marker。

测试覆盖：

- 纯 JSON；
- Markdown 代码块中的 JSON；
- 前后带说明文字的 JSON；
- 合法模型输出；
- 越界值；
- 缺失字段；
- 非 JSON 输出；
- service 集成；
- Receiver 隐私投影。

## 当前回归测试状态

目前报告的 Phase 1–5B 测试全部通过：

- `test_db.py`；
- `test_state_machine.py`；
- `test_metrics.py`；
- `test_acoustic_bridge.py`；
- `test_service.py`；
- `test_server.py`；
- `test_real_osc.py`；
- `test_real_model.py`。

自动化系统已经具备进行真实 VCV 排练的条件，但真实浏览器和真实 VCV patch 的最终验收尚未完成。

## 当前架构

```text
浏览器 / HTTP 客户端
        ↓
server.py
        ↓
service.py
        ├── state_machine.py
        ├── db.py → SQLite
        ├── real_model.py / FakeModelBackend
        ├── acoustic_bridge.py
        └── real_osc.py / FakeOscTransport
                         ↓
                       VCV Rack
```

## 待完成工作

### Phase 5C — 真实 VCV 与现场排练

- 确认真实 VCV patch 响应全部 8 个 OSC 地址；
- 现场验证中性状态和极端 VAD 状态；
- 验证多个 marker 之间声音持续运行；
- 验证音量安全、无爆音和削波；
- 用录屏核对 marker 时间；
- 完成双浏览器完整实验；
- 验证 Settlement 后 VCV 是否停止或进入安全 idle 状态。

### Phase 6 — 前端

待实现文件：

- `web/index.html`；
- `web/style.css`；
- `web/app.js`；
- `web/coords.js`；
- `web/revelation.js`。

前端只能消费现有 HTTP projection，不得重新定义状态机逻辑。

## 仍需冻结的决定

1. 确认 `inter_round_drift` 是否继续使用归一化欧氏距离，而不是原计划中的余弦距离；
2. 确认 metrics 和 voltage helper 的直接调用是否统一采用严格拒绝，而不是 clamp；
3. `/api/blind/summary` 应使用 session token，或改为一次性 reveal token；
4. 确认真实 VCV patch 中 8 个 OSC 地址与模块端口的对应关系；
5. 确认 Settlement 后 VCV 是停止还是进入安全 idle；
6. 确认录屏中显示的 marker 格式。

## 开发纪律

- 保留 Fake backend，保证自动化测试稳定；
- Real model 和 Real OSC 必须继续通过抽象接口接入；
- 模型和网络调用不得放在 SQLite transaction 内；
- 不自动修改 VCV patch；
- 未获得明确授权时不执行 Git commit；
- 每个阶段完成后继续运行全部历史回归测试。
