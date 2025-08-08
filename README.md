# OpenRouter King v1.0.0

一个强大的GitHub API密钥扫描工具，专门用于发现和验证各种AI服务的API密钥，包括OpenRouter、OpenAI、Anthropic Claude、Google Gemini等。

**版本**: 1.0.0  
**发布日期**: 2025-08-08  
**作者**: xmdbd  
**仓库**: https://github.com/xmdbd/openrouter-king

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
   git clone https://github.com/xmdbd/openrouter-king.git
   cd openrouter-king
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

## ⚡ 极简运行（推荐新手）

如果你只想快速体验，可以使用这个最简单的方式：

### Windows 用户
```cmd
# 1. 下载项目
git clone https://github.com/xmdbd/openrouter-king.git
cd openrouter-king

# 2. 安装依赖
pip install flask flask-cors requests

# 3. 直接运行
python app.py
```

### Linux/Mac 用户
```bash
# 方式1: 一键运行脚本（推荐）
curl -sSL https://raw.githubusercontent.com/xmdbd/openrouter-king/main/quick-start.sh | bash

# 方式2: 手动执行（使用虚拟环境）
git clone https://github.com/xmdbd/openrouter-king.git && cd openrouter-king
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors requests
python app.py

# 方式3: 系统包安装（Ubuntu/Debian）
git clone https://github.com/xmdbd/openrouter-king.git && cd openrouter-king
sudo apt update
sudo apt install python3-flask python3-flask-cors python3-requests
python3 app.py
```

### 访问应用
1. 浏览器打开：http://localhost:4567
2. 点击标题10次进入管理面板
3. 输入密码：`Kuns123456.`
4. 添加你的GitHub Token开始扫描

**就这么简单！** 🎉

### 🔄 后台运行（关闭终端也不会停止）

如果你想让程序在后台运行，不受终端关闭影响：

#### 方法1: 使用 nohup（最简单）
```bash
# 先按上面步骤安装和激活虚拟环境
git clone https://github.com/xmdbd/openrouter-king.git && cd openrouter-king
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors requests

# 后台运行
nohup python app.py > app.log 2>&1 &

# 查看日志
tail -f app.log

# 停止程序
pkill -f "python app.py"
```

#### 方法2: 使用 screen（推荐）
```bash
# 安装 screen
sudo apt install screen    # Ubuntu/Debian
sudo yum install screen     # CentOS/RHEL

# 创建 screen 会话
screen -S openrouter

# 在 screen 中运行程序（按上面的完整步骤）
git clone https://github.com/xmdbd/openrouter-king.git && cd openrouter-king
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors requests
python app.py

# 分离会话（程序继续运行）: 按 Ctrl+A 然后按 D
# 重新连接: screen -r openrouter
# 列出会话: screen -ls
```

#### 方法3: 使用 tmux
```bash
# 安装 tmux
sudo apt install tmux      # Ubuntu/Debian

# 创建会话
tmux new -s openrouter

# 在 tmux 中运行程序
git clone https://github.com/xmdbd/openrouter-king.git && cd openrouter-king
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors requests
python app.py

# 分离会话: 按 Ctrl+B 然后按 D
# 重新连接: tmux attach -t openrouter
```

#### 方法4: 一键后台启动脚本（最推荐）
```bash
# 🚀 一键启动后台服务
curl -sSL https://raw.githubusercontent.com/xmdbd/openrouter-king/main/start-background.sh | bash

# 🔍 检查服务状态  
curl -sSL https://raw.githubusercontent.com/xmdbd/openrouter-king/main/check-status.sh | bash

# 🛑 停止服务
curl -sSL https://raw.githubusercontent.com/xmdbd/openrouter-king/main/stop.sh | bash
```

这个方法会：
- 自动下载项目到 `~/openrouter-king`
- 创建虚拟环境和安装依赖
- 后台启动服务（关闭终端不影响）
- 生成PID文件便于管理
- 提供完整的日志记录

### 常见问题
- **遇到 `externally-managed-environment` 错误？** 
  查看 [安装问题解决指南](install.md)
- **权限不足？** 在命令前加 `sudo`
- **找不到模块？** 确保已激活虚拟环境：`source venv/bin/activate`
- **关闭终端程序就停了？** 使用上面的后台运行方法

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
   apt install python3 python3-pip python3-venv python3-full git -y
   # 可选：直接安装系统包
   apt install python3-flask python3-flask-cors python3-requests -y
   
   # CentOS/RHEL
   yum update -y
   yum install python3 python3-pip git -y
   ```

3. **克隆项目到服务器**
   ```bash
   cd /opt
   git clone https://github.com/xmdbd/openrouter-king.git
   cd openrouter-king
   ```

4. **安装Python依赖**
   ```bash
   # 方式1: 使用虚拟环境（推荐）
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # 方式2: 系统包安装（Ubuntu/Debian）
   sudo apt install python3-flask python3-flask-cors python3-requests
   
   # 方式3: 强制安装到系统（不推荐）
   pip3 install -r requirements.txt --break-system-packages
   ```

5. **创建systemd服务文件**
   ```bash
   cat > /etc/systemd/system/openrouter-king.service << EOF
   [Unit]
   Description=OpenRouter King Scanner Service
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/opt/openrouter-king
   ExecStart=/opt/openrouter-king/venv/bin/python app.py
   Restart=always
   RestartSec=10
   Environment=FLASK_ENV=production
   Environment=PATH=/opt/openrouter-king/venv/bin:/usr/local/bin:/usr/bin:/bin

   [Install]
   WantedBy=multi-user.target
   EOF
   ```

6. **启动并启用服务**
   ```bash
   systemctl daemon-reload
   systemctl start openrouter-king
   systemctl enable openrouter-king
   systemctl status openrouter-king
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
   
   **注意**: 首次部署后建议立即修改默认密码以确保安全性

### 方式二：使用 screen/tmux 后台运行

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
   cd /opt/openrouter-king
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
   # 创建备份目录
   mkdir -p /backup
   
   # 创建备份脚本
   cat > /opt/backup.sh << 'EOF'
   #!/bin/bash
   # 备份数据库
   cp /opt/openrouter-king/app.db /backup/app.db.$(date +%Y%m%d_%H%M%S)
   
   # 删除7天前的备份
   find /backup -name "app.db.*" -mtime +7 -delete
   
   # 记录备份日志
   echo "$(date): Database backup completed" >> /var/log/backup.log
   EOF
   
   chmod +x /opt/backup.sh
   
   # 添加到crontab (每天凌晨2点备份)
   echo "0 2 * * * /opt/backup.sh" | crontab -
   ```

### 故障排除

1. **查看服务日志**
   ```bash
   # systemd服务
   journalctl -u openrouter-king -f
   
   # screen会话
   screen -r scanner
   ```

2. **检查端口占用**
   ```bash
   netstat -tlnp | grep 4567
   lsof -i:4567
   ```

3. **权限问题**
   ```bash
   chmod 755 /opt/openrouter-king
   chmod 644 /opt/openrouter-king/app.db
   ```

4. **Python依赖问题**
   ```bash
   # 虚拟环境方式
   cd /opt/openrouter-king
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install flask flask-cors requests
   
   # 系统包方式
   sudo apt install python3-flask python3-flask-cors python3-requests
   
   # 强制安装方式（最后选择）
   pip3 install flask flask-cors requests --break-system-packages
   ```

5. **服务无法启动**
   ```bash
   # 检查Python路径
   which python3
   
   # 检查服务文件语法
   systemd-analyze verify /etc/systemd/system/openrouter-king.service
   
   # 手动测试启动
   cd /opt/openrouter-king
   # 如果使用虚拟环境
   source venv/bin/activate && python app.py
   # 或者直接使用系统Python
   python3 app.py
   ```

## ⚙️ 配置说明

### 管理员配置
- 默认管理员密码：`Kuns123456.`
- 登录后可配置GitHub Token和扫描参数

### 扫描参数
- **扫描间隔**：120秒（默认，可调整）
- **每查询结果数**：100个
- **时间范围**：365天内的仓库
- **查询总数**：28个精选查询

### 查询分布
- **OpenRouter查询**：10个（专项搜索）
- **OpenAI查询**：8个（全面覆盖）
- **Anthropic查询**：3个（精选重点）
- **Gemini查询**：4个（高价值目标）
- **通用配置文件**：3个（兜底搜索）

## 📊 性能指标

### 扫描能力
- **完整周期**：约15-20分钟
- **日循环次数**：72-96轮
- **日扫描容量**：200,000+个文件
- **发现效率**：高质量密钥发现，智能过滤误报

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
openrouter-king/
├── app.py              # 主应用程序
├── requirements.txt    # Python依赖
├── README.md           # 项目文档
├── VERSION             # 版本号
├── CHANGELOG.md        # 更新日志
├── quick-start.sh      # Linux/Mac快速启动脚本
├── quick-start.bat     # Windows快速启动脚本
├── start-background.sh # 后台启动脚本
├── check-status.sh     # 状态检查脚本
├── stop.sh            # 停止服务脚本
├── install.md          # 安装问题解决指南
├── app.db              # SQLite数据库（自动生成）
├── static/             # 静态资源
│   ├── css/
│   │   └── app.css     # 样式文件
│   └── js/
│       └── app.js      # 前端逻辑
└── templates/          # HTML模板
    └── index.html      # Web界面
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

### 提交Issue
- 在 [GitHub Issues](https://github.com/xmdbd/openrouter-king/issues) 提交问题
- 详细描述问题和复现步骤
- 提供相关日志和截图

### 贡献代码
1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](https://github.com/xmdbd/openrouter-king/blob/main/LICENSE) 文件。

## ⚠️ 免责声明

本工具仅供安全研究和教育目的使用。使用者应：
- 遵守相关法律法规
- 尊重API服务商的使用条款
- 负责任地使用发现的密钥信息
- 不得用于恶意目的

使用本工具产生的任何后果由使用者承担。

## 📞 联系与支持

- **GitHub**: [@xmdbd](https://github.com/xmdbd)
- **Issues**: [提交问题](https://github.com/xmdbd/openrouter-king/issues)
- **仓库**: [openrouter-king](https://github.com/xmdbd/openrouter-king)

## ⭐ Star History

如果这个项目对你有帮助，请给一个 Star ⭐ 支持一下！

---

**Made with ❤️ by [xmdbd](https://github.com/xmdbd)**

**Happy Scanning! 🔍✨**