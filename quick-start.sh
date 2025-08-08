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
if command -v pip3 >/dev/null 2>&1; then
    pip3 install flask flask-cors requests
elif command -v pip >/dev/null 2>&1; then
    pip install flask flask-cors requests
else
    echo "❌ 请先安装 pip"
    exit 1
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
python3 app.py