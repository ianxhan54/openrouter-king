# 安装问题解决指南

## Python 环境管理问题

### 错误：externally-managed-environment

如果遇到以下错误：
```
error: externally-managed-environment
× This environment is externally managed
```

这是因为较新的 Linux 发行版（如 Ubuntu 23.04+、Debian 12+）为了系统稳定性，限制了直接使用 pip 安装到系统 Python 环境。

### 解决方案

#### 方案1: 使用虚拟环境（推荐）
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install flask flask-cors requests

# 运行应用
python app.py
```

#### 方案2: 使用系统包管理器
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-flask python3-flask-cors python3-requests

# 直接运行
python3 app.py
```

#### 方案3: 使用 pipx（应用程序安装）
```bash
# 安装 pipx
sudo apt install pipx

# 为当前项目创建隔离环境
mkdir -p ~/.local/share/openrouter-king
cd ~/.local/share/openrouter-king
git clone https://github.com/xmdbd/openrouter-king.git .
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors requests
python app.py
```

#### 方案4: 强制安装（不推荐）
```bash
pip3 install flask flask-cors requests --break-system-packages
```

⚠️ **注意**: 方案4可能会影响系统稳定性，仅在其他方案不可用时使用。

### 不同系统的最佳实践

#### Ubuntu 24.04 / Debian 12+
```bash
# 推荐：系统包 + 虚拟环境混合
sudo apt install python3-flask python3-flask-cors python3-requests
git clone https://github.com/xmdbd/openrouter-king.git
cd openrouter-king
python3 app.py
```

#### CentOS/RHEL/Rocky Linux
```bash
# 通常可以直接使用 pip
pip3 install flask flask-cors requests
```

#### macOS
```bash
# 使用 Homebrew
brew install python
pip3 install flask flask-cors requests

# 或使用虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors requests
```

### 生产环境部署

对于生产环境，推荐使用虚拟环境：

```bash
cd /opt/openrouter-king
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors requests

# systemd 服务文件使用虚拟环境的 Python
ExecStart=/opt/openrouter-king/venv/bin/python app.py
```

### 检查当前环境

```bash
# 检查 Python 版本
python3 --version

# 检查是否在虚拟环境中
echo $VIRTUAL_ENV

# 检查已安装的包
pip list | grep -E "(flask|requests)"
```