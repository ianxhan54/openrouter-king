#!/bin/bash

# OpenRouter King 停止脚本

WORK_DIR="$HOME/openrouter-king"
PID_FILE="$WORK_DIR/app.pid"
LOG_FILE="$WORK_DIR/app.log"

echo "🛑 OpenRouter King 停止脚本"
echo "========================="

# 检查PID文件
if [ ! -f "$PID_FILE" ]; then
    echo "⭕ 服务未运行（无PID文件）"
    
    # 尝试查找并终止可能的孤儿进程
    PIDS=$(pgrep -f "python.*app.py" || true)
    if [ -n "$PIDS" ]; then
        echo "🔍 发现可能的相关进程: $PIDS"
        echo "是否要终止这些进程? (y/n)"
        read -r response
        if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
            kill $PIDS
            echo "✅ 已终止相关进程"
        fi
    fi
    exit 0
fi

# 读取PID
PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ps -p "$PID" > /dev/null 2>&1; then
    echo "🔄 正在停止服务 (PID: $PID)..."
    
    # 优雅停止
    kill "$PID"
    
    # 等待进程结束
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        echo "   等待进程结束... ($i/10)"
        sleep 1
    done
    
    # 检查是否成功停止
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  优雅停止失败，强制终止..."
        kill -9 "$PID"
        sleep 2
    fi
    
    # 最终检查
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "❌ 无法停止进程 $PID"
        exit 1
    else
        echo "✅ 服务已停止"
        rm -f "$PID_FILE"
        
        if [ -f "$LOG_FILE" ]; then
            echo "📋 最后的日志:"
            echo "----------------------------------------"
            tail -5 "$LOG_FILE"
        fi
    fi
else
    echo "⭕ 进程 $PID 不存在（可能已经停止）"
    rm -f "$PID_FILE"
fi

echo ""
echo "🚀 重新启动命令:"
echo "   curl -sSL https://raw.githubusercontent.com/xmdbd/openrouter-king/main/start-background.sh | bash"