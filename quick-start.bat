@echo off
:: OpenRouter King 快速启动脚本 (Windows)
chcp 65001 >nul

echo 🚀 OpenRouter King 快速启动脚本
echo =================================

:: 检查Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 请先安装 Python
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 请先安装 Git
    echo 下载地址: https://git-scm.com/downloads
    pause
    exit /b 1
)

:: 创建临时目录
set TEMP_DIR=%TEMP%\openrouter-king-%RANDOM%
echo 📁 创建临时目录: %TEMP_DIR%
mkdir "%TEMP_DIR%"
cd /d "%TEMP_DIR%"

:: 克隆项目
echo 📥 下载项目...
git clone https://github.com/xmdbd/openrouter-king.git
cd openrouter-king

:: 安装依赖
echo 📦 安装依赖...
pip install flask flask-cors requests

echo.
echo ✅ 安装完成！
echo.
echo 🎯 启动信息：
echo    - Web界面: http://localhost:4567
echo    - 管理密码: Kuns123456.
echo    - 进入管理: 点击标题10次
echo.
echo ⚠️  注意: 请先配置GitHub Token才能开始扫描
echo.
echo 🚀 正在启动应用...
echo    按 Ctrl+C 停止运行
echo =================================
echo.

:: 启动应用
python app.py

pause