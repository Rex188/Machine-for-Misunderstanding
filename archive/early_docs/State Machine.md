## 核心原则

- Session 状态由服务器决定；
- 客户端只能提交事件，不能直接改状态；
- 发送者和接收者看到的是同一个服务器状态的不同投影；
- 每一轮只包含一次声音传输；
- 任意一方可以结束，但继续下一轮必须双方同意。
- 音频引擎在 session 开始后持续运行；
- 下一次有效输入会改变声音参数；
- 音频切片只用于数据记录，不作为交互阻塞条件；
- 接收者不需要等待音频停止；
- 实验轮次仍然必须顺序完成；
- 前端倒计时、音频结束事件和固定播放时长全部删除。
---
## 一轮的定义

> 一轮 =
Sender提交文本与自评VAD
→ 模型解释
→ 声音参数更新
→ Receiver提交听觉感受与VAD
→ 本轮完成
## Workflow

### 实验SM和音频SM
```mermaid
stateDiagram-v2
    [*] --> LOBBY

    LOBBY --> READY: 两名参与者连接
    READY --> INPUT_OPEN: 双方确认开始

    INPUT_OPEN --> MODEL_PROCESSING: Sender提交文本与自评VAD

    MODEL_PROCESSING --> SOUND_UPDATE: 模型成功且输出有效
    MODEL_PROCESSING --> ERROR: 模型失败或超时

    SOUND_UPDATE --> RECEIVER_RESPONSE: 声音参数更新成功

    RECEIVER_RESPONSE --> ROUND_COMPLETE: Receiver提交感受与VAD
    RECEIVER_RESPONSE --> ERROR: 提交无效或会话超时

    ROUND_COMPLETE --> SETTLEMENT: 任一方选择结束
    ROUND_COMPLETE --> SETTLEMENT: 达到最大轮数
    ROUND_COMPLETE --> NEXT_ROUND_PENDING: 双方请求继续

    NEXT_ROUND_PENDING --> INPUT_OPEN: 双方同意继续
    NEXT_ROUND_PENDING --> SETTLEMENT: 任一方选择结束
    NEXT_ROUND_PENDING --> SETTLEMENT: 任一方超时

    ERROR --> MODEL_PROCESSING: 可恢复的模型错误
    ERROR --> SOUND_UPDATE: 可恢复的音频更新错误
    ERROR --> RECEIVER_RESPONSE: 可恢复的客户端错误
    ERROR --> ABORTED: 无法恢复

    SETTLEMENT --> [*]
    ABORTED --> [*]

    note right of SOUND_UPDATE
        更新持续播放的声音
        创建或切换 audio segment
        不等待音频停止
    end note

    note right of SETTLEMENT
        停止音频引擎
        关闭当前 audio segment
        生成完整导出数据
    end note
```
```mermaid
stateDiagram-v2
	[*] --> STOPPED

    STOPPED --> STARTING: Session开始
    STARTING --> RUNNING: 音频设备与VCV连接成功
    STARTING --> ERROR: 初始化失败

    RUNNING --> SEGMENT_ROTATION: 收到新的有效输入

    SEGMENT_ROTATION --> RUNNING: 关闭旧切片并开始新切片
    SEGMENT_ROTATION --> ERROR: 切片写入或OSC更新失败

    RUNNING --> STOPPING: Session结束
    RUNNING --> ERROR: 音频设备、录音或OSC异常

    ERROR --> RUNNING: 错误恢复
    ERROR --> STOPPING: 放弃当前Session

    STOPPING --> STOPPED: 停止播放并保存当前切片
    STOPPED --> [*]

    note right of RUNNING
        音乐持续播放
        等待下一次输入
        不存在15秒自动停止
    end note

    note right of SEGMENT_ROTATION
        1. 记录旧segment的end_at
        2. 保存或关闭旧音频文件
        3. 更新OSC参数
        4. 创建新的audio segment
        5. 可选短crossfade
    end note
```

状态机关系

实验状态机进入 SOUND_UPDATE
        ↓
音频状态机收到“更新声音”事件
        ↓
执行 SEGMENT_ROTATION
        ↓
返回 RUNNING
        ↓
实验状态机进入 RECEIVER_RESPONSE



Round 1:
A sender → B receiver

Round 2:
B sender → A receiver

Round 3:
A sender → B receiver

每轮角色写进日志，避免后续重建错误。