#!/bin/bash

# OpenRouter King 运行问题修复脚本

echo "🔧 OpenRouter King 运行问题修复脚本"
echo "====================================="

# 1. 停止所有相关进程
echo "🛑 停止现有进程..."
pkill -f "python.*app.py" 2>/dev/null || true
sleep 2

# 强制停止端口占用
PORT_PID=$(lsof -ti:4567 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "   强制停止端口4567的进程: $PORT_PID"
    kill -9 $PORT_PID 2>/dev/null || true
fi

# 2. 清理临时文件和PID
echo "🧹 清理临时文件..."
rm -rf /tmp/openrouter-king-* 2>/dev/null || true
rm -f ~/openrouter-king/app.pid 2>/dev/null || true
rm -f ~/openrouter-king/nohup.out 2>/dev/null || true

# 3. 检查现有安装
if [ -d ~/openrouter-king ]; then
    echo "📁 发现现有安装: ~/openrouter-king"
    echo "   选择操作:"
    echo "   1) 更新现有安装 (推荐)"
    echo "   2) 重新安装 (删除重建)"
    echo "   3) 修复现有安装"
    read -p "   请选择 (1-3): " choice
    
    case $choice in
        1)
            echo "📥 更新现有安装..."
            cd ~/openrouter-king
            git pull origin main || {
                echo "⚠️  Git更新失败，尝试重新克隆..."
                cd ~
                rm -rf openrouter-king
                git clone https://github.com/xmdbd/openrouter-king.git
                cd openrouter-king
            }
            ;;
        2)
            echo "🗑️  删除旧安装..."
            rm -rf ~/openrouter-king
            echo "📥 重新克隆项目..."
            cd ~
            git clone https://github.com/xmdbd/openrouter-king.git
            cd ~/openrouter-king
            ;;
        3)
            echo "🔧 修复现有安装..."
            cd ~/openrouter-king
            ;;
        *)
            echo "❌ 无效选择，默认更新现有安装"
            cd ~/openrouter-king
            git pull origin main || true
            ;;
    esac
else
    echo "📥 未发现现有安装，克隆新项目..."
    cd ~
    git clone https://github.com/xmdbd/openrouter-king.git
    cd ~/openrouter-king
fi

# 4. 设置虚拟环境
echo "🐍 设置Python虚拟环境..."
if [ -d "venv" ]; then
    echo "   发现现有虚拟环境，重新创建..."
    rm -rf venv
fi

python3 -m venv venv
source venv/bin/activate

# 5. 安装依赖
echo "📦 安装/更新依赖..."
pip install --upgrade pip
pip install flask flask-cors requests

# 6. 检查配置
echo "🔍 检查应用配置..."
if [ -f "app.py" ]; then
    echo "   ✅ 主程序文件存在"
else
    echo "   ❌ 主程序文件缺失"
    exit 1
fi

# 7. 启动服务
echo "🚀 启动服务..."
nohup python app.py > app.log 2>&1 &
PID=$!
echo $PID > app.pid

# 等待启动
echo "⏳ 等待服务启动..."
sleep 5

# 检查启动状态
if ps -p $PID > /dev/null 2>&1; then
    echo "✅ 服务启动成功!"
    echo ""
    echo "📊 服务信息:"
    echo "   PID: $PID"
    echo "   访问地址: http://localhost:4567"
    echo "   日志文件: $(pwd)/app.log"
    echo "   停止命令: kill $PID"
    echo ""
    echo "🔧 管理命令:"
    echo "   查看日志: tail -f $(pwd)/app.log"
    echo "   检查状态: ps -p $PID"
    echo "   重启服务: kill $PID && nohup python app.py > app.log 2>&1 &"
    echo ""
    echo "📋 最近日志:"
    tail -5 app.log
else
    echo "❌ 服务启动失败"
    echo ""
    echo "错误日志:"
    echo "--------"
    cat app.log 2>/dev/null || echo "无日志文件"
    echo ""
    echo "🔧 手动启动命令:"
    echo "   cd ~/openrouter-king"
    echo "   source venv/bin/activate"
    echo "   python app.py"
    rm -f app.pid
fi