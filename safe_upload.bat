@echo off
echo ========================================
echo    Hajimi King 安全上传检查脚本
echo ========================================
echo.

echo [1/4] 检查敏感文件...
if exist .env (
    echo ⚠️  警告: 发现 .env 文件！
    echo    建议: 删除或重命名为 .env.backup
    set /p confirm="是否继续？(y/n): "
    if /i not "%confirm%"=="y" exit /b 1
)

if exist data\keys_valid*.txt (
    echo ⚠️  警告: 发现密钥文件在 data 文件夹！
    echo    建议: 清理 data 文件夹
    set /p confirm="是否继续？(y/n): "
    if /i not "%confirm%"=="y" exit /b 1
)

echo ✅ 敏感文件检查通过
echo.

echo [2/4] 初始化 Git 仓库...
git init
echo ✅ Git 初始化完成
echo.

echo [3/4] 添加安全文件...
git add *.py
git add *.md
git add requirements*.txt
git add Dockerfile*
git add docker-compose*.yml
git add .gitignore
git add .env.example 2>nul
git add .env.optimized
git add queries.example
git add app\
git add utils\
git add common\
git add templates\ 2>nul
git add safe_upload.bat
echo ✅ 文件添加完成
echo.

echo [4/4] 最终检查...
echo ========================================
git status --short
echo ========================================
echo.
echo 请检查上面的文件列表：
echo   - 不应该有 .env 文件
echo   - 不应该有 data/ 文件夹内容
echo   - 不应该有真实的密钥文件
echo.

set /p ready="确认无敏感信息，准备提交？(y/n): "
if /i "%ready%"=="y" (
    git commit -m "Hajimi King - OpenRouter API key scanner optimized version"
    echo.
    echo ✅ 提交成功！
    echo.
    echo 下一步：
    echo 1. 在 GitHub 创建新仓库
    echo 2. 运行: git remote add origin https://github.com/你的用户名/仓库名.git
    echo 3. 运行: git push -u origin main
) else (
    echo.
    echo 已取消提交。请检查文件后重试。
)

pause