# 🔧 错误修复指南

## 问题：Failed to fetch file content: HTTPError

### 错误描述
```
❌ Failed to fetch file content: https://api.github.com/repos/xxx/contents/env, HTTPError
```

### 原因分析

1. **文件不存在（404）**
   - 文件可能已被删除
   - 文件路径错误
   - 文件名缺少扩展名（如 `env` 实际是 `.env`）

2. **访问限制（403）**
   - GitHub Token权限不足
   - 达到API速率限制
   - 仓库设置了访问限制

3. **网络问题**
   - 连接超时
   - 代理配置错误

### 解决方案

#### 使用增强版GitHub工具类

已创建 `utils/github_utils_enhanced.py`，提供以下改进：

1. **多策略获取文件**
   - 先尝试API获取
   - 失败后尝试raw.githubusercontent.com
   - 自动尝试添加常见扩展名

2. **智能错误处理**
   - 详细的错误日志
   - 自动Token轮换
   - 失败Token标记和跳过

3. **改进的重试机制**
   - 指数退避
   - 连接池复用
   - 自动恢复

### 快速修复步骤

#### 方法1：替换现有模块

```python
# 在 app/hajimi_king.py 中修改导入
# 原来：
from utils.github_utils import GitHubUtils

# 改为：
from utils.github_utils_enhanced import EnhancedGitHubUtils as GitHubUtils
```

#### 方法2：使用新的优化版本

```bash
# 直接运行优化版，已包含所有修复
python app/hajimi_king_optimized.py
```

### 配置优化建议

```ini
# .env 文件配置

# 增加更多Token以分散请求
GITHUB_TOKENS=token1,token2,token3,token4,token5

# 增加重试次数
MAX_RETRIES=5

# 增加超时时间
REQUEST_TIMEOUT=30

# 如果在中国，考虑使用代理
PROXY=http://your-proxy:port
```

### 常见错误代码含义

| 状态码 | 含义 | 解决方法 |
|--------|------|----------|
| 400 | 请求格式错误 | 检查查询语法 |
| 401 | Token无效 | 更新GitHub Token |
| 403 | 访问被拒绝 | 检查Token权限或等待限流恢复 |
| 404 | 文件不存在 | 正常情况，文件可能已删除 |
| 422 | 参数错误 | 检查搜索参数 |
| 429 | 速率限制 | 等待或使用更多Token |

### 监控和诊断

#### 查看Token状态
增强版会自动记录Token使用统计：

```python
# 获取统计信息
stats = github_utils.get_token_statistics()
print(stats)
# 输出：
# {
#   "tokens": [
#     {"token": "ghp_xxx...", "success": 100, "failure": 5, "success_rate": "95.2%"},
#     ...
#   ],
#   "failed_count": 1
# }
```

#### 启用详细日志
```ini
# .env
LOG_LEVEL=DEBUG
DEBUG_MODE=true
```

### 预防措施

1. **定期检查Token有效性**
```bash
# 测试脚本
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
```

2. **监控API限额**
```bash
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit
```

3. **使用多个Token轮换**
   - 每个Token每小时5000次请求
   - 5个Token = 25000次/小时

4. **优化搜索查询**
   - 更精确的搜索词减少无效结果
   - 使用文件类型过滤：`extension:env`
   - 限制仓库大小：`size:<1000`

### 紧急恢复

如果所有Token都失效：

1. **生成新Token**
   - 访问 https://github.com/settings/tokens
   - 创建新的Personal Access Token
   - 只需要 `public_repo` 权限

2. **临时降级运行**
```ini
# 减少并发和请求频率
CONCURRENT_VALIDATORS=1
VALIDATION_DELAY_MIN=2.0
VALIDATION_DELAY_MAX=5.0
```

3. **使用备用策略**
   - 只扫描最近更新的仓库
   - 跳过大文件和二进制文件
   - 使用更保守的重试策略

---

**注意**：增强版模块向后兼容，可以直接替换原有模块使用。建议在遇到频繁错误时切换到增强版。