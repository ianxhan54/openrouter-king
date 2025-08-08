# OpenRouter API Key Scanner

一个强大的GitHub API密钥扫描工具，专门用于发现和验证各种AI服务的API密钥，包括OpenRouter、OpenAI、Anthropic Claude、Google Gemini等。

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

### 安装步骤

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
   - 打开浏览器访问：http://localhost:8080
   - 使用管理员密码登录配置Token

## ⚙️ 配置说明

### 管理员配置
- 默认管理员密码：`Lcg040510.`
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