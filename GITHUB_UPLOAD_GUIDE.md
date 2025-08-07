# 📤 GitHub 上传安全指南

## ⚠️ **上传前必读 - 安全检查清单**

### ❌ **绝对不要上传的文件**

| 文件 | 原因 | 检查命令 |
|------|------|----------|
| `.env` | 包含你的 GitHub tokens | `type .env` |
| `data/` 文件夹 | 包含扫描到的密钥 | `dir data` |
| `queries.txt` | 你的个人搜索策略 | `type queries.txt` |
| `*.db` | 数据库包含敏感数据 | `dir *.db` |
| `keys_valid_*.txt` | 发现的有效密钥 | `dir keys_valid_*.txt` |

### ✅ **安全上传步骤**

## 1️⃣ **清理敏感数据**

```bash
# Windows 命令
cd D:\项目\hajimi-king-main

# 1. 检查 .env 文件是否包含真实 token
type .env
# 如果有真实 token，删除或重置为示例值

# 2. 清理数据文件夹
rmdir /s /q data
mkdir data

# 3. 确保 queries.txt 不包含敏感信息
copy queries.example queries.txt

# 4. 检查是否有其他敏感文件
dir /s *.env
dir /s *token*
dir /s *key*
```

## 2️⃣ **创建示例配置文件**

```bash
# 确保 .env.example 存在且不包含真实 token
copy .env.optimized .env.example

# 编辑 .env.example，将所有真实值替换为示例
notepad .env.example
# 替换为：
# GITHUB_TOKENS=ghp_example1,ghp_example2,ghp_example3
```

## 3️⃣ **验证 .gitignore 文件**

```bash
# 确认 .gitignore 正确配置
type .gitignore

# 测试 .gitignore 是否生效
git status
# 不应该看到 .env, data/ 等敏感文件
```

## 4️⃣ **初始化 Git 仓库**

```bash
# 初始化
git init

# 添加远程仓库
git remote add origin https://github.com/你的用户名/hajimi-king.git

# 检查状态（重要！）
git status
```

## 5️⃣ **安全提交**

```bash
# 添加文件（注意不要用 git add .）
git add *.py
git add *.md
git add requirements*.txt
git add Dockerfile*
git add docker-compose*.yml
git add .gitignore
git add .env.example
git add .env.optimized
git add queries.example
git add app/
git add utils/
git add common/

# 再次检查
git status
# 确保没有 .env 或 data/ 等敏感文件

# 提交
git commit -m "Initial commit - Hajimi King optimized version"

# 推送
git push -u origin main
```

## 6️⃣ **上传后验证**

访问你的 GitHub 仓库，确认：
- ❌ 没有 `.env` 文件
- ❌ 没有 `data/` 文件夹
- ❌ 没有任何包含真实 token 的文件
- ✅ 有 `.env.example` 示例文件
- ✅ 有 `.gitignore` 文件

## 🔒 **额外安全措施**

### 1. 使用 GitHub Secrets（如果需要 CI/CD）

```yaml
# .github/workflows/scan.yml
env:
  GITHUB_TOKENS: ${{ secrets.GITHUB_TOKENS }}
```

### 2. 扫描泄露的密钥

```bash
# 安装 gitleaks
# https://github.com/zricethezav/gitleaks

# 扫描本地仓库
gitleaks detect --source . -v

# 扫描历史提交
gitleaks detect --source . --log-level debug
```

### 3. 如果不小心上传了敏感信息

```bash
# 立即执行！

# 1. 删除远程仓库的文件
git rm --cached .env
git rm -r --cached data/
git commit -m "Remove sensitive files"
git push

# 2. 清理历史记录（如果已经提交）
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# 3. 强制推送
git push origin --force --all

# 4. 立即更换泄露的 tokens！
# 访问 https://github.com/settings/tokens
# 删除旧 token，创建新的
```

## 📝 **README.md 建议内容**

在你的 README.md 中添加：

```markdown
## 🔒 安全说明

本项目用于安全研究和教育目的。

### ⚠️ 重要提醒
- **永远不要**提交真实的 API tokens 到仓库
- **永远不要**上传扫描结果到公开仓库
- 使用 `.env.example` 作为配置模板
- 所有敏感数据应保存在本地

### 🚀 使用方法
1. 克隆仓库
2. 复制 `.env.example` 到 `.env`
3. 添加你自己的 GitHub tokens
4. 运行程序
```

## ✅ **最终检查清单**

上传前，确保：

- [ ] `.env` 文件已删除或在 `.gitignore` 中
- [ ] `data/` 文件夹已清空或在 `.gitignore` 中
- [ ] 没有真实的 API tokens 在任何文件中
- [ ] `.gitignore` 文件配置正确
- [ ] 有 `.env.example` 示例文件
- [ ] `git status` 不显示敏感文件
- [ ] README 包含安全警告

## 🚨 **紧急联系**

如果不小心泄露了 token：
1. 立即到 GitHub 删除/禁用 token
2. 使用上面的命令清理 git 历史
3. 创建新的 token
4. 检查是否有人使用了你的 token

---

**记住：安全第一！宁可多检查几次，也不要泄露敏感信息。**