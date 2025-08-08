#!/bin/bash

# OpenRouter King 状态检查脚本

WORK_DIR="$HOME/openrouter-king"
PID_FILE="$WORK_DIR/app.pid"
LOG_FILE="$WORK_DIR/app.log"

echo "🔍 OpenRouter King 状态检查"
echo "=========================="

# 检查工作目录
if [ ! -d "$WORK_DIR" ]; then
    echo "❌ 项目未安装"
    echo "   请先运行启动脚本: curl -sSL https://raw.githubusercontent.com/xmdbd/openrouter-king/main/start-background.sh | bash"
    exit 1
fi

# 检查PID文件
if [ ! -f "$PID_FILE" ]; then
    echo "⭕ 服务未运行（无PID文件）"
    echo "   启动服务: curl -sSL https://raw.githubusercontent.com/xmdbd/openrouter-king/main/start-background.sh | bash"
    exit 1
fi

# 读取PID
PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ps -p "$PID" > /dev/null 2>&1; then
    echo "✅ 服务正在运行"
    echo ""
    echo "📊 服务信息:"
    echo "   PID: $PID"
    echo "   运行时间: $(ps -o etime= -p "$PID" | tr -d ' ')"
    echo "   内存使用: $(ps -o rss= -p "$PID" | tr -d ' ') KB"
    echo "   访问地址: http://localhost:4567"
    
    # 检查端口
    if command -v netstat >/dev/null 2>&1; then
        if netstat -tlnp 2>/dev/null | grep ":4567" >/dev/null; then
            echo "   端口状态: ✅ 4567 端口正在监听"
        else
            echo "   端口状态: ⚠️ 4567 端口未监听"
        fi
    fi
    
    echo ""
    echo "🔧 管理命令:"
    echo "   查看日志: tail -f $LOG_FILE"
    echo "   停止服务: kill $PID"
    echo "   重启服务: kill $PID && curl -sSL https://raw.githubusercontent.com/xmdbd/openrouter-king/main/start-background.sh | bash"
    
    # 显示最近日志
    if [ -f "$LOG_FILE" ]; then
        echo ""
        echo "📋 最近日志 (最后10行):"
        echo "----------------------------------------"
        tail -10 "$LOG_FILE"
    fi
    
    echo ""
    echo "🌐 Web访问测试:"
    if command -v curl >/dev/null 2>&1; then
        if curl -s "http://localhost:4567" >/dev/null; then
            echo "   ✅ Web服务响应正常"
        else
            echo "   ❌ Web服务无响应"
        fi
    else
        echo "   请手动访问: http://localhost:4567"
    fi
else
    echo "❌ 服务已停止 (PID $PID 不存在)"
    rm -f "$PID_FILE"
    echo "   重新启动: curl -sSL https://raw.githubusercontent.com/xmdbd/openrouter-king/main/start-background.sh | bash"
fi