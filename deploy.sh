#!/bin/bash
set -e

# ============================
# Hajimi King 优化版部署脚本
# ============================

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Hajimi King Optimized Deployment...${NC}"

# 1. 检查Docker和Docker Compose
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Error: docker is not installed.${NC}"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}Error: docker-compose is not installed.${NC}"; exit 1; }
echo -e "${GREEN}✅ Docker and Docker Compose are installed.${NC}"

# 2. 检查配置文件
if [ ! -f .env.optimized ]; then
    echo -e "${RED}Error: .env.optimized not found. Please create it from the example.${NC}"
    exit 1
fi

# 复制配置文件（如果不存在）
if [ ! -f .env ]; then
    echo -e "${YELLOW}Copying .env.optimized to .env...${NC}"
    cp .env.optimized .env
fi
echo -e "${GREEN}✅ Configuration file is ready.${NC}"

# 3. 检查GitHub Tokens
if ! grep -q "GITHUB_TOKENS=" .env || grep -q "ghp_token1" .env; then
    echo -e "${YELLOW}Warning: GITHUB_TOKENS are not configured in .env.${NC}"
    read -p "Enter your GitHub tokens (comma-separated): " tokens
    # 使用sed进行原地替换
    sed -i "s/GITHUB_TOKENS=.*/GITHUB_TOKENS=$tokens/" .env
    echo -e "${GREEN}✅ GitHub tokens have been configured.${NC}"
fi

# 4. 创建数据目录
if [ ! -d "data" ]; then
    echo -e "${YELLOW}Creating data directory...${NC}"
    mkdir -p data
    chmod 777 data  # 确保容器内的非root用户有权限写入
fi
echo -e "${GREEN}✅ Data directory is ready.${NC}"

# 5. 构建Docker镜像
echo -e "${YELLOW}Building Docker image (this may take a while)...${NC}"
docker-compose -f docker-compose.optimized.yml build

# 6. 启动服务
echo -e "${GREEN}Starting Hajimi King service...${NC}"
docker-compose -f docker-compose.optimized.yml up -d

echo -e "
${GREEN}🎉 Deployment complete!${NC}"
echo -e "-----------------------------------"
echo -e "✅ Hajimi King is running in the background."
echo -e "📈 Web Monitor: http://localhost:5001"
echo -e "-----------------------------------"
echo -e "
${YELLOW}Useful commands:${NC}"
echo -e "  - View logs: ${GREEN}docker-compose -f docker-compose.optimized.yml logs -f${NC}"
echo -e "  - Stop service: ${GREEN}docker-compose -f docker-compose.optimized.yml down${NC}"
echo -e "  - Check status: ${GREEN}docker-compose -f docker-compose.optimized.yml ps${NC}"
echo -e "  - Enter container: ${GREEN}docker-compose -f docker-compose.optimized.yml exec hajimi-king /bin/bash${NC}"
echo -e "
${YELLOW}To view results:${NC}"
echo -e "  - Valid keys are in: ${GREEN}data/keys/keys_valid_*.txt${NC}"
echo -e "  - Detailed logs in: ${GREEN}data/logs/keys_valid_detail_*.log${NC}"
echo -e "  - Database file: ${GREEN}data/hajimi_king.db${NC}"
echo -e "
${YELLOW}Enjoy Hajimi King! 👑${NC}"
