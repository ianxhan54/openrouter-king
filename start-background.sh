#!/bin/bash

# OpenRouter King 后台启动脚本

set -e

echo "🚀 OpenRouter King 后台启动脚本"
echo "====================================="

# 检查必要工具
command -v git >/dev/null 2>&1 || { echo "❌ 请先安装 git"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ 请先安装 Python3"; exit 1; }

# 设置工作目录
WORK_DIR="$HOME/openrouter-king"
PID_FILE="$WORK_DIR/app.pid"
LOG_FILE="$WORK_DIR/app.log"

echo "📁 工作目录: $WORK_DIR"

# 检查是否已经在运行
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  程序已经在运行中 (PID: $PID)"
        echo "   访问地址: http://localhost:4567"
        echo "   查看日志: tail -f $LOG_FILE"
        echo "   停止程序: kill $PID"
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# 创建/进入工作目录
if [ ! -d "$WORK_DIR" ]; then
    echo "📥 下载项目到 $WORK_DIR..."
    git clone https://github.com/xmdbd/openrouter-king.git "$WORK_DIR"
else
    echo "📂 使用现有项目目录"
    cd "$WORK_DIR"
    git pull origin main >/dev/null 2>&1 || echo "   (更新跳过)"
fi

cd "$WORK_DIR"

# 设置虚拟环境
if [ ! -d "venv" ]; then
    echo "🔧 创建虚拟环境..."
    python3 -m venv venv
fi

echo "📦 安装/更新依赖..."
source venv/bin/activate
pip install --quiet flask flask-cors requests

echo "🚀 启动后台服务..."

# 后台启动并记录PID
nohup python app.py > "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

# 等待启动
sleep 3

# 检查启动状态
if ps -p "$PID" > /dev/null 2>&1; then
    echo "✅ 启动成功!"
    echo ""
    echo "📊 服务信息:"
    echo "   PID: $PID"
    echo "   访问地址: http://localhost:4567"
    echo "   日志文件: $LOG_FILE"
    echo "   PID文件: $PID_FILE"
    echo ""
    echo "🔧 管理命令:"
    echo "   查看日志: tail -f $LOG_FILE"
    echo "   停止服务: kill $PID"
    echo "   重启服务: kill $PID && $0"
    echo ""
    echo "⚠️  注意: 首次使用需要配置 GitHub Token"
    echo "   1. 访问 http://localhost:4567"
    echo "   2. 点击标题10次进入管理面板"  
    echo "   3. 输入密码: Kuns123456."
    echo "   4. 配置你的 GitHub Token"
    echo ""
    echo "📋 最近日志:"
    tail -5 "$LOG_FILE"
else
    echo "❌ 启动失败"
    echo "查看错误日志: cat $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi