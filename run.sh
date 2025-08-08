#!/usr/bin/env bash
set -euo pipefail

# 最简一键启动脚本（无需设置环境变量）
# 可选：在此处设置端口、监听等（取消注释以覆盖默认值）
# export HOST=0.0.0.0
# export PORT=5000
# export DEBUG=false
# export SCANNER_DB_PATH=./scanner.db
# export ALLOWED_ORIGINS=*
# export OPENROUTER_VALIDATION_ENDPOINT=https://openrouter.ai/api/v1/auth/key
# export OPENROUTER_TIMEOUT=10
# export ADMIN_BEARER=your-secret-token

python web_scanner.py

