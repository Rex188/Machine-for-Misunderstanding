#!/usr/bin/env bash
# ==============================================================================
# launch_performance.sh — Project 2: A Machine for Misunderstanding
# 专为表演设计的“一键无脑启动”控制脚本
#
# 功能：
#   1. 自动定位项目根目录与 Conda blindtest 环境
#   2. 自动检查 VCV Rack (UDP 7001) 状态
#   3. 自动清理旧的 7070 / 8080 残留端口
#   4. 自动以时间戳生成全新独立的数据库文件与 Session ID
#   5. 后台并发启动 API Server (Port 7070) 与 Web Static Server (Port 8080)
#   6. 自动在浏览器中以两个独立窗口/标签页打开 Participant A 与 Participant B
#   7. 控制台清晰打印 A/B 登录凭据与运行日志
#   8. 按 Ctrl+C 时自动优雅停止所有后台子服务并安全退出
# ==============================================================================

set -e

# 定位脚本所在目录（blind_test 目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "   🌌 A Machine for Misunderstanding · Performance Launch System"
echo "======================================================================"

# 1. 查找 Python 解释器 (优先使用 blindtest 环境)
CONDA_PYTHON="/Users/rexli/miniforge3/envs/blindtest/bin/python"
if [ -x "$CONDA_PYTHON" ]; then
    PYTHON_BIN="$CONDA_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "❌ [错误] 未找到 Python 解释器！"
    exit 1
fi
echo "🐍 Python 解释器 : $PYTHON_BIN"

# 2. 检查 VCV Rack (UDP 7001)
if lsof -nP -iUDP:7001 >/dev/null 2>&1; then
    echo "🎛️  VCV Rack 状态  : [正常] UDP 7001 正在监听"
else
    echo "⚠️  [提示] 未检测到 VCV Rack 监听 UDP 7001！"
    echo "    请确认已打开: /Users/rexli/Documents/Rex/portfolio/project2/workflow/generative template new mvp.vcv"
    echo "    (若仅进行网络与界面测试可继续，但现场表演发声需打开 VCV Rack)"
    echo "----------------------------------------------------------------------"
    read -p "按 Enter 键继续启动系统，或按 Ctrl+C 退出后打开 VCV Rack..." _
fi

# 3. 端口清理 (7070 & 8080)
echo "🧹 检查并释放旧端口..."
P7070=$(lsof -ti:7070 2>/dev/null || true)
if [ -n "$P7070" ]; then
    echo "   清理旧 API 服务 (PID: $P7070)..."
    kill -9 $P7070 2>/dev/null || true
fi

P8080=$(lsof -ti:8080 2>/dev/null || true)
if [ -n "$P8080" ]; then
    echo "   清理旧 Web 静态服务 (PID: $P8080)..."
    kill -9 $P8080 2>/dev/null || true
fi
sleep 0.5

# 4. 模型后端检测 (支持本地 Qwen 与云端 DeepSeek)
if [ -z "$DEEPSEEK_API_KEY" ] && [ -f "data/deepseek.key" ]; then
    export DEEPSEEK_API_KEY=$(cat data/deepseek.key | tr -d '[:space:]')
fi

# 5. 自定义轮数与生成本次演出的全新 Session
if [ -n "$1" ] && [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -gt 0 ]; then
    export MAX_ROUNDS="$1"
elif [ -z "$MAX_ROUNDS" ]; then
    echo "----------------------------------------------------------------------"
    read -t 15 -p "🎯 请设置本场演出的轮数上限 [默认 10 轮，直接按 Enter 默认]: " USER_INPUT_ROUNDS || true
    echo ""
    if [ -n "$USER_INPUT_ROUNDS" ] && [[ "$USER_INPUT_ROUNDS" =~ ^[0-9]+$ ]] && [ "$USER_INPUT_ROUNDS" -gt 0 ]; then
        export MAX_ROUNDS="$USER_INPUT_ROUNDS"
    else
        export MAX_ROUNDS=10
    fi
fi

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
export DB_FILE="data/perf_${TIMESTAMP}.db"
export SESSION_ID="s_perf_${TIMESTAMP}"
export TOKEN_A="token-A-${TIMESTAMP}"
export TOKEN_B="token-B-${TIMESTAMP}"
export PARTICIPANT_A="p_${SESSION_ID}_A"
export PARTICIPANT_B="p_${SESSION_ID}_B"

mkdir -p data

# 初始化数据库并创建 Session
PYTHONPATH=. "$PYTHON_BIN" -c "
import os
from db import Database
db = Database(os.environ['DB_FILE'])
db.init_db()
max_r = int(os.environ.get('MAX_ROUNDS', 10))
db.create_session(session_id=os.environ['SESSION_ID'], max_rounds=max_r)
"

# 固化本次配置到 current_perf.env
cat <<EOF > data/current_perf.env
export DB_FILE="$DB_FILE"
export SESSION_ID="$SESSION_ID"
export TOKEN_A="$TOKEN_A"
export TOKEN_B="$TOKEN_B"
export PARTICIPANT_A="$PARTICIPANT_A"
export PARTICIPANT_B="$PARTICIPANT_B"
export MAX_ROUNDS="$MAX_ROUNDS"
export DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY"
EOF

echo "📁 实验数据库   : $DB_FILE"
echo "🆔 会话 ID      : $SESSION_ID"
echo "🎯 轮数设定     : 上限 $MAX_ROUNDS 轮 (每轮完成后双方可点击【继续下一轮】，亦可随时点击【结束结算】生成报告)"
if [ -n "$DEEPSEEK_API_KEY" ]; then
    echo "🧠 意图翻译模型 : ☁️  云端 DeepSeek API (deepseek-chat)"
else
    echo "🧠 意图翻译模型 : 💻 本地 Qwen2.5-1.5B + LoRA (未配置 DEEPSEEK_API_KEY)"
fi
echo "======================================================================"
echo "🔑 本次演出的登录凭据（已为您生成，浏览器打开后填入对应窗口即可）："
echo ""
echo "   【Participant A (先发声 Sender)】"
echo "   Session ID : $SESSION_ID"
echo "   Slot       : Participant A"
echo "   Token      : $TOKEN_A"
echo ""
echo "   【Participant B (先聆听 Receiver)】"
echo "   Session ID : $SESSION_ID"
echo "   Slot       : Participant B"
echo "   Token      : $TOKEN_B"
echo "======================================================================"

# 获取当前局域网 IP (Wi-Fi 或以太网)
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")

# 5. 启动后台服务
# 5.1 启动 API Server (监听 0.0.0.0:7070 允许局域网外部电脑访问)
PYTHONPATH=. "$PYTHON_BIN" -c "
import os
from db import Database
from service import BlindTestService
from real_model import LocalQwenBackend, DeepSeekBackend
from real_osc import RealOscTransport
from server import create_server

db = Database(os.environ['DB_FILE'])
db.init_db()

use_ds = bool(os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('USE_DEEPSEEK') == '1')
if use_ds and os.environ.get('DEEPSEEK_API_KEY'):
    print('🧠 [Model Backend] 启用云端 DeepSeek API 后端')
    model_backend = DeepSeekBackend()
else:
    print('🧠 [Model Backend] 启用本地 Qwen2.5-1.5B+LoRA 后端')
    model_backend = LocalQwenBackend()

service = BlindTestService(
    db=db,
    model_backend=model_backend,
    osc_transport=RealOscTransport(host='127.0.0.1', port=7001),
)
server = create_server(host='0.0.0.0', port=7070, service=service, long_poll_timeout=20.0)
server.serve_forever()
" > data/api_server.log 2>&1 &
API_PID=$!

# 5.2 启动 Web Server (监听 0.0.0.0:8080)
PYTHONPATH=. "$PYTHON_BIN" -m http.server 8080 --bind 0.0.0.0 --directory web > data/web_server.log 2>&1 &
WEB_PID=$!

# 退出捕获：确保 Ctrl+C 时杀死两个后台服务
cleanup() {
    echo ""
    echo "🛑 正在安全停止表演服务..."
    kill -9 "$API_PID" 2>/dev/null || true
    kill -9 "$WEB_PID" 2>/dev/null || true
    echo "✓ 服务已完全退出，端口已释放。"

    # 若本次有完成轮次，自动读取真实 DB 生成可视化图表并预览
    if [ -f "$DB_FILE" ]; then
        echo "📊 正在从本次演出数据库生成高保真分析图表..."
        "$PYTHON_BIN" generate_summary_chart.py "$DB_FILE" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 6. 等待端口就绪并健康检查
echo "⏳ 等待服务初始化与模型预载..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:7070/api/blind/health >/dev/null 2>&1 && curl -s http://127.0.0.1:8080/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

if ! curl -s http://127.0.0.1:7070/api/blind/health >/dev/null 2>&1; then
    echo "❌ API 服务启动超时，请查看日志: cat data/api_server.log"
    exit 1
fi
echo "✓ API Server (Port 7070) 就绪！"
echo "✓ Web Server (Port 8080) 就绪！"
echo ""

# 7. 自动打开浏览器窗口
echo "🌐 正在为您本机打开 Participant A 浏览器界面..."
open "http://127.0.0.1:8080/"

echo ""
echo "🎉 系统已全部就绪！"
echo "======================================================================"
echo "💻【主机 A（你的电脑：发声 + 模型 + VCV）】"
echo "   网页地址 : http://127.0.0.1:8080/ (已自动在浏览器打开)"
echo "   操作角色 : 勾选 Participant A"
echo "   会话凭据 : Session ID = $SESSION_ID  |  Token = $TOKEN_A"
echo "----------------------------------------------------------------------"
echo "💻【副机 B（另一台电脑：受听参与者）】"
echo "   请确保副机与本机连接同一个 Wi-Fi (局域网) 或手机热点！"
echo "   在副机浏览器输入 : http://${LAN_IP}:8080/"
echo "   操作角色 : 勾选 Participant B"
echo "   会话凭据 : Session ID = $SESSION_ID  |  Token = $TOKEN_B"
echo "======================================================================"
echo "（按 Ctrl + C 可随时退出并自动停止所有服务）"
echo "----------------------------------------------------------------------"
echo "实时服务输出流（按 Ctrl+C 退出）："

# 跟踪日志输出
tail -f data/api_server.log
