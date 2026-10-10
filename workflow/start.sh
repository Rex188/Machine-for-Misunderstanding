#!/usr/bin/env bash
# ==============================================================================
# start.sh — Project 2: A Machine for Misunderstanding 一键启动总枢纽
#
# 功能：
#   1. 自动选择最佳 Python 环境 (Miniforge3 Apple Silicon Metal MPS 加速)
#   2. 启动 Web 控制中心与声音可视化服务 (http://127.0.0.1:7070)
#   3. 自动在系统默认浏览器中打开 Web 可视化界面
#   4. 前台保持服务常驻，并实时流式输出模型推理与 VCV OSC 调度日志
#   5. 按 Ctrl+C 安全退出并释放端口
# ==============================================================================

# 解析软链接真实物理目标路径并定位到 workflow 目录
TARGET="${BASH_SOURCE[0]}"
while [ -L "$TARGET" ]; do
    DIR="$(cd -P "$(dirname "$TARGET")" && pwd)"
    TARGET="$(readlink "$TARGET")"
    [[ $TARGET != /* ]] && TARGET="$DIR/$TARGET"
done
RESOLVED_DIR="$(cd -P "$(dirname "$TARGET")" && pwd)"

if [ -f "$RESOLVED_DIR/llm_sound_interactive.py" ]; then
    WORKFLOW_DIR="$RESOLVED_DIR"
elif [ -d "$RESOLVED_DIR/workflow" ]; then
    WORKFLOW_DIR="$RESOLVED_DIR/workflow"
else
    WORKFLOW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/workflow" 2>/dev/null && pwd)"
fi

cd "$WORKFLOW_DIR" || { echo "❌ 无法定位 workflow 目录"; exit 1; }
SCRIPT_DIR="$WORKFLOW_DIR"

# 查找 Python 解释器 (优先使用已配置好 PyTorch MPS 的 Miniforge3)
if [ -x "/Users/rexli/miniforge3/bin/python3" ]; then
    PYTHON_BIN="/Users/rexli/miniforge3/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "❌ [错误] 未找到可用 Python 3 环境！"
    exit 1
fi

echo "======================================================================"
echo "   🌌 A Machine for Misunderstanding · 系统一键启动"
echo "======================================================================"
echo "🐍 Python 解释器 : $PYTHON_BIN"
echo "🧠 模型后端     : 本地微调 Qwen2.5-1.5B (LoRA on Metal MPS)"
echo "🎛️ OSC 发送目标 : 127.0.0.1:7001 (VCV Rack cvOSCcv)"
echo "🌐 访问网址     : http://127.0.0.1:7070"
echo "======================================================================"

# 启用本地微调模型
export USE_LOCAL_MODEL=1

# 清理旧的 7070 端口占用
OLD_PID=$(lsof -ti:7070 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "⚠️ 发现旧 Web 服务进程占用端口 7070 (PID: $OLD_PID)，正在清理..."
    kill -9 "$OLD_PID" 2>/dev/null
    sleep 0.5
fi

# 在后台启动延迟打开浏览器的任务 (等待 1.5 秒确保服务已就绪)
(
    sleep 1.5
    echo ""
    echo "🌐 [系统] 正在自动唤起默认浏览器打开 http://127.0.0.1:7070 ..."
    if command -v open >/dev/null 2>&1; then
        open "http://127.0.0.1:7070"
    fi
) &

echo "🚀 [系统] 正在启动后端服务，按 Ctrl+C 可随时停止服务..."
echo "----------------------------------------------------------------------"

# 前台直接运行 Web 控制器与模型服务，实时输出日志，绝不会静默退出！
exec "$PYTHON_BIN" web_controller_server.py
