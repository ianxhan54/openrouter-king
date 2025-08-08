#!/bin/bash

# OpenRouter King 快速启动脚本
# 适用于 Linux/Mac 系统

set -e

echo "🚀 OpenRouter King 快速启动脚本"
echo "================================="

# 检查是否安装了必要工具
command -v git >/dev/null 2>&1 || { echo "❌ 请先安装 git"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ 请先安装 Python3"; exit 1; }

# 创建临时目录
TEMP_DIR="/tmp/openrouter-king-$(date +%s)"
echo "📁 创建临时目录: $TEMP_DIR"
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

# 克隆项目
echo "📥 下载项目..."
git clone https://github.com/xmdbd/openrouter-king.git
cd openrouter-king

# 安装依赖
echo "📦 安装依赖..."

# 检测系统类型并选择最佳安装方式
if [ -f /etc/debian_version ]; then
    # Debian/Ubuntu 系统
    echo "🐧 检测到 Debian/Ubuntu 系统"
    
    # 尝试系统包管理器安装
    if command -v apt >/dev/null 2>&1; then
        echo "   使用 apt 安装系统包..."
        sudo apt update >/dev/null 2>&1
        if sudo apt install -y python3-flask python3-flask-cors python3-requests >/dev/null 2>&1; then
            echo "✅ 使用系统包安装成功"
        else
            echo "⚠️  系统包安装失败，尝试虚拟环境..."
            python3 -m venv venv
            source venv/bin/activate
            pip install flask flask-cors requests
        fi
    else
        echo "   创建虚拟环境..."
        python3 -m venv venv
        source venv/bin/activate
        pip install flask flask-cors requests
    fi
else
    # 其他系统使用 pip 或虚拟环境
    echo "🖥️  通用系统，使用 pip 安装..."
    
    # 尝试直接 pip 安装
    if pip3 install flask flask-cors requests >/dev/null 2>&1; then
        echo "✅ pip 安装成功"
    elif pip install flask flask-cors requests >/dev/null 2>&1; then
        echo "✅ pip 安装成功"
    else
        echo "⚠️  pip 安装失败，创建虚拟环境..."
        python3 -m venv venv
        source venv/bin/activate
        pip install flask flask-cors requests
    fi
fi

echo "✅ 安装完成！"
echo ""
echo "🎯 启动信息："
echo "   - Web界面: http://localhost:4567"
echo "   - 管理密码: Kuns123456."
echo "   - 进入管理: 点击标题10次"
echo ""
echo "⚠️  注意: 请先配置GitHub Token才能开始扫描"
echo ""
echo "🚀 正在启动应用..."
echo "   按 Ctrl+C 停止运行"
echo "================================="

# 启动应用
if [ -f "venv/bin/activate" ]; then
    echo "🔥 使用虚拟环境启动..."
    source venv/bin/activate
    python app.py
else
    echo "🔥 使用系统 Python 启动..."
    python3 app.py
fi