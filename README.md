# OpenRouter API Key Scanner v1.0.0

一个强大的GitHub API密钥扫描工具，专门用于发现和验证各种AI服务的API密钥，包括OpenRouter、OpenAI、Anthropic Claude、Google Gemini等。

**版本**: 1.0.0  
**发布日期**: 2025-08-08

## 🌟 特性

### 核心功能
- **多平台支持**：扫描OpenRouter、OpenAI、Anthropic、Gemini等主流AI服务密钥
- **智能验证**：自动验证密钥有效性，区分有效、无效、被限流等状态
- **实时监控**：24/7持续扫描，Web界面实时显示扫描状态和结果
- **平衡策略**：17分钟完成一轮扫描，每天约86轮循环
- **数据持久化**：SQLite数据库存储，支持数据导出

### 扫描引擎
- **基于Example架构**：采用久经验证的扫描算法
- **智能去重**：SHA缓存避免重复扫描相同文件
- **上下文过滤**：自动过滤占位符和示例密钥
- **速率限制友好**：智能延迟控制，避免触发GitHub API限制
- **Token轮换**：支持多个GitHub Token轮换使用

### Web界面
- **实时仪表盘**：显示扫描统计、密钥数量、有效率等
- **自动刷新**：可配置的自动刷新间隔（3-60秒）
- **分类查看**：按平台和状态分类显示密钥
- **数据导出**：支持按状态导出密钥到TXT文件
- **移动友好**：响应式设计，支持各种设备

## 🚀 快速开始

### 环境要求
- Python 3.8+
- GitHub Personal Access Token

### 本地安装

1. **克隆项目**
   ```bash
   git clone https://github.com/your-repo/openrouter-scanner.git
   cd openrouter-scanner
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置GitHub Token**
   - 访问 [GitHub Settings > Tokens](https://github.com/settings/tokens)
   - 创建Personal Access Token (经典版本)
   - 勾选 `public_repo` 权限
   - 复制生成的token

4. **启动应用**
   ```bash
   python app.py
   ```

5. **访问Web界面**
   - 打开浏览器访问：http://localhost:4567
   - 使用管理员密码登录配置Token

## 🌐 云服务器部署

### 方式一：使用 systemd 服务（推荐用于生产环境）

1. **连接到云服务器**
   ```bash
   ssh root@your-server-ip
   ```

2. **安装Python和Git**
   ```bash
   # Ubuntu/Debian
   apt update && apt upgrade -y
   apt install python3 python3-pip git -y
   
   # CentOS/RHEL
   yum update -y
   yum install python3 python3-pip git -y
   ```

3. **克隆项目到服务器**
   ```bash
   cd /opt
   git clone https://github.com/your-repo/openrouter-scanner.git
   cd openrouter-scanner
   ```

4. **安装Python依赖**
   ```bash
   pip3 install -r requirements.txt
   ```

5. **创建systemd服务文件**
   ```bash
   cat > /etc/systemd/system/openrouter-scanner.service << EOF
   [Unit]
   Description=OpenRouter API Key Scanner
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/opt/openrouter-scanner
   ExecStart=/usr/bin/python3 /opt/openrouter-scanner/app.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   EOF
   ```

6. **启动并启用服务**
   ```bash
   systemctl daemon-reload
   systemctl start openrouter-scanner
   systemctl enable openrouter-scanner
   systemctl status openrouter-scanner
   ```

7. **配置防火墙**
   ```bash
   # Ubuntu/Debian (ufw)
   ufw allow 4567/tcp
   ufw reload
   
   # CentOS/RHEL (firewalld)
   firewall-cmd --permanent --add-port=4567/tcp
   firewall-cmd --reload
   ```

8. **访问应用**
   - 浏览器访问：http://your-server-ip:4567
   - 使用管理员密码 `Kuns123456.` 登录

### 方式二：使用 Docker 容器

1. **安装Docker**
   ```bash
   curl -fsSL https://get.docker.com | sh
   systemctl start docker
   systemctl enable docker
   ```

2. **创建Dockerfile**
   ```bash
   cat > Dockerfile << EOF
   FROM python:3.9-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   EXPOSE 4567
   CMD ["python", "app.py"]
   EOF
   ```

3. **构建并运行容器**
   ```bash
   docker build -t openrouter-scanner .
   docker run -d \
     --name scanner \
     --restart always \
     -p 4567:4567 \
     -v $(pwd)/app.db:/app/app.db \
     openrouter-scanner
   ```

### 方式三：使用 screen/tmux 后台运行

1. **安装screen**
   ```bash
   apt install screen -y  # Ubuntu/Debian
   yum install screen -y  # CentOS/RHEL
   ```

2. **创建新的screen会话**
   ```bash
   screen -S scanner
   ```

3. **在screen中运行应用**
   ```bash
   cd /opt/openrouter-scanner
   python3 app.py
   ```

4. **分离screen会话**
   - 按 `Ctrl+A` 然后按 `D` 分离会话
   - 重新连接：`screen -r scanner`

### 安全建议

1. **使用Nginx反向代理（可选）**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://127.0.0.1:4567;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. **配置SSL证书（推荐）**
   ```bash
   # 使用Let's Encrypt免费证书
   apt install certbot python3-certbot-nginx -y
   certbot --nginx -d your-domain.com
   ```

3. **修改默认密码**
   - 编辑 `app.py` 文件
   - 修改 `ADMIN_PASSWORD` 变量
   - 重启服务

4. **定期备份数据库**
   ```bash
   # 创建备份脚本
   echo '#!/bin/bash
   cp /opt/openrouter-scanner/app.db /backup/app.db.$(date +%Y%m%d)
   find /backup -name "app.db.*" -mtime +7 -delete' > /opt/backup.sh
   chmod +x /opt/backup.sh
   
   # 添加到crontab
   echo "0 2 * * * /opt/backup.sh" | crontab -
   ```

### 故障排除

1. **查看服务日志**
   ```bash
   # systemd服务
   journalctl -u openrouter-scanner -f
   
   # Docker容器
   docker logs -f scanner
   ```

2. **检查端口占用**
   ```bash
   netstat -tlnp | grep 4567
   lsof -i:4567
   ```

3. **权限问题**
   ```bash
   chmod 755 /opt/openrouter-scanner
   chmod 644 /opt/openrouter-scanner/app.db
   ```

4. **Python依赖问题**
   ```bash
   pip3 install --upgrade pip
   pip3 install -r requirements.txt --force-reinstall
   ```

## ⚙️ 配置说明

### 管理员配置
- 默认管理员密码：`Kuns123456.`
- 登录后可配置GitHub Token和扫描参数

### 扫描参数
- **扫描间隔**：40秒（可调整）
- **每查询结果数**：100个
- **时间范围**：365天内的仓库
- **查询总数**：25个精选查询

### 查询分布
- **Gemini查询**：5个（优先级最高）
- **OpenAI查询**：6个（全面覆盖）
- **Anthropic查询**：4个（精选重点）
- **OpenRouter查询**：3个（专项搜索）
- **通用查询**：7个（兜底搜索）

## 📊 性能指标

### 扫描能力
- **完整周期**：16.7分钟
- **日循环次数**：86轮
- **日扫描容量**：216,000个文件
- **发现效率**：高质量密钥发现

### 验证精度
- **OpenRouter验证**：使用实际聊天API验证
- **OpenAI验证**：模型列表API验证
- **Gemini验证**：生成API验证
- **Anthropic验证**：模型API验证

## 🛡️ 安全特性

### 密钥验证
- **真实验证**：使用各平台实际API进行验证
- **状态跟踪**：记录有效、无效、限流等详细状态
- **余额查询**：支持OpenRouter余额查询

### 数据安全
- **本地存储**：所有数据存储在本地SQLite数据库
- **加密传输**：使用HTTPS与各API平台通信
- **访问控制**：管理员密码保护敏感操作

## 📁 项目结构

```
openrouter-scanner/
├── app.py              # 主应用程序
├── app.db              # SQLite数据库
├── static/             # 静态资源
│   ├── css/app.css     # 样式文件
│   └── js/app.js       # JavaScript逻辑
├── templates/          # HTML模板
│   └── index.html      # 主页面
└── example/            # 参考实现
    ├── app/hajimi_king.py
    └── utils/
```

## 🔧 API端点

### 配置管理
- `GET /api/config` - 获取配置
- `POST /api/config` - 更新配置（需管理员权限）

### 密钥管理
- `GET /api/keys` - 获取所有密钥
- `GET /api/keys_grouped` - 按类型分组获取密钥
- `GET /api/keys/export/<provider>` - 导出指定平台密钥
- `GET /api/keys/export/<provider>/<status>` - 按状态导出密钥

### 统计监控
- `GET /api/stats` - 获取扫描统计
- `GET /api/scanner/status` - 获取扫描器状态
- `POST /api/scanner/trigger` - 手动触发扫描

## 📈 使用统计

### 典型发现率
- **OpenRouter密钥**：100%发现但验证后多数无效
- **Gemini密钥**：较高的有效率
- **OpenAI密钥**：中等发现率和有效率
- **Anthropic密钥**：相对较少但质量较高

### 扫描覆盖
- **文件类型**：.env, .json, .js, .py等配置文件
- **仓库类型**：公开仓库，1年内活跃
- **过滤策略**：自动排除文档、示例、测试目录

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进项目！

### 开发环境
1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

### 代码规范
- 遵循PEP 8 Python编码规范
- JavaScript使用ES6+语法
- 添加适当的注释和文档

## 📄 许可证

本项目采用MIT许可证，详见LICENSE文件。

## ⚠️ 免责声明

本工具仅供安全研究和教育目的使用。使用者应：
- 遵守相关法律法规
- 尊重API服务商的使用条款
- 负责任地使用发现的密钥信息
- 不得用于恶意目的

使用本工具产生的任何后果由使用者承担。

## 📞 支持

如有问题或建议，请：
- 提交GitHub Issue
- 发送邮件至开发者
- 查看项目Wiki获取更多信息

---

**Happy Scanning! 🔍✨**