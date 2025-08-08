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
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
import base64
import random

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

app_start_time = datetime.now()
scanner_start_time: Optional[datetime] = None

# Token 状态跟踪（内存）
token_status: Dict[str, Dict[str, Any]] = {}

def mark_token_status(token: str, status: str, code: Optional[int] = None):
    try:
        token_status[token] = {
            'status': status,
            'code': code,
            'ts': datetime.now().isoformat(timespec='seconds')
        }
    except Exception:
        pass

# 全局变量
scanner_thread = None
scanner_running = False
config = {
    'github_tokens': [],
    'scan_queries': [
        # OpenRouter
        '"sk-or-v1-" extension:json',
        '"sk-or-v1-" extension:env',
        '"sk-or-" filename:.env',
        '"openrouter" "api_key"',
        '"OPENROUTER_API_KEY"',
        '"sk-or-"',
        # OpenAI
        '"OPENAI_API_KEY"',
        'openai "api_key"',
        '"sk-" filename:.env',
        '"sk-" extension:env',
        'openai sk- extension:py',
        # Anthropic (Claude)
        '"ANTHROPIC_API_KEY"',
        'anthropic "api_key"',
        '"sk-ant-"',
        # Google Gemini
        '"GEMINI_API_KEY"',
        '"AIzaSy"',
        'generativelanguage.googleapis.com "key="'
    ],
    'scan_interval': 60,  # 秒
    'max_results_per_query': 100,
    'path_blacklist': ["/docs/", "/doc/", "/example/", "/samples/", ".md", "/tests/", "/spec/", "/tutorial"]
}


# 数据库初始化
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_value TEXT UNIQUE,
            key_type TEXT,
            balance REAL,
            limit_amount REAL,
            is_free_tier BOOLEAN,
            source_repo TEXT,
            source_url TEXT,
            found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checked TIMESTAMP
        )
    ''')
    # 迁移：若旧表缺少 key_type 列，则补充
    try:
        c.execute("PRAGMA table_info(keys)")
        cols = [r[1] for r in c.fetchall()]
        if 'key_type' not in cols:
            c.execute("ALTER TABLE keys ADD COLUMN key_type TEXT")
    except Exception:
        pass
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
# 计数器工具

def inc_counter(name: str, delta: int = 1):
    try:
        cur = _config_get(name, 0)
        if not isinstance(cur, int):
            cur = 0
        _config_set(name, cur + delta)
    except Exception:
        pass


def get_counter(name: str, default: int = 0) -> int:
    try:
        val = _config_get(name, default)
        return int(val) if isinstance(val, (int, float, str)) and str(val).isdigit() else default
    except Exception:
        return default



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


# 简单指数退避
def backoff_sleep(attempt: int, base: float = 0.5, cap: float = 8.0):
    delay = min(cap, base * (2 ** attempt))
    time.sleep(delay + random.uniform(0, 0.3))

# 多厂商Key提取
KEY_PATTERNS = {
    'openrouter': r'(sk-or-[A-Za-z0-9\-_]{20,60})',
    'openai': r'(sk-[A-Za-z0-9]{20,50})',
    'anthropic': r'(sk-ant-[A-Za-z0-9\-_]{20,60})',
    'gemini': r'(AIzaSy[A-Za-z0-9\-_]{33})',
}

def extract_keys_by_provider(content: str) -> Dict[str, List[str]]:
    found: Dict[str, List[str]] = {k: [] for k in KEY_PATTERNS.keys()}
    for provider, pattern in KEY_PATTERNS.items():
        try:
            matches = re.findall(pattern, content)
            if matches:
                found[provider] = list(set(matches))
        except re.error:
            continue
    return found
def validate_openai_key(api_key: str) -> Dict:
    """验证 OpenAI API Key（最小权限：列出模型），含429退避"""
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        for attempt in range(3):
            resp = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)
            if resp.status_code == 429:
                backoff_sleep(attempt)
                continue
            if resp.status_code == 200:
                return {"valid": True, "type": "openai"}
            if resp.status_code in (401, 403):
                return {"valid": False}
            return {"valid": False}
        return {"valid": False}
    except Exception as e:
        log_message(f"OpenAI验证失败: {str(e)}", "error")
        return {"valid": False}


def validate_anthropic_key(api_key: str) -> Dict:
    """验证 Anthropic API Key（最小权限：列出模型），含429退避"""
    try:
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        for attempt in range(3):
            resp = requests.get("https://api.anthropic.com/v1/models", headers=headers, timeout=10)
            if resp.status_code == 429:
                backoff_sleep(attempt)
                continue
            if resp.status_code == 200:
                return {"valid": True, "type": "anthropic"}
            if resp.status_code in (401, 403):
                return {"valid": False}
            return {"valid": False}
        return {"valid": False}
    except Exception as e:
        log_message(f"Anthropic验证失败: {str(e)}", "error")
        return {"valid": False}


def validate_gemini_key(api_key: str) -> Dict:
    """验证 Google Gemini API Key（最小权限：列出模型），含429退避"""
    try:
        for attempt in range(3):
            url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 429:
                backoff_sleep(attempt)
                continue
            if resp.status_code == 200:
                return {"valid": True, "type": "gemini"}
            if resp.status_code in (400, 401, 403):
                return {"valid": False}
            return {"valid": False}
        return {"valid": False}
    except Exception as e:
        log_message(f"Gemini验证失败: {str(e)}", "error")
        return {"valid": False}

            continue
    return found

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
# 轮换 GitHub tokens 的搜索（处理403/429）

def search_github_any(query: str) -> (List[Dict], Optional[str]):
    tokens = [t.strip() for t in (config.get('github_tokens') or []) if t.strip()]
    if not tokens:
        return [], None
    start = random.randrange(0, len(tokens))
    for i in range(len(tokens)):
        token = tokens[(start + i) % len(tokens)]
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        try:
            resp = requests.get(
                "https://api.github.com/search/code",
                headers=headers,
                params={"q": query, "per_page": 100},
                timeout=30
            )
            # 正常
            if resp.status_code == 200:
                data = resp.json()
                mark_token_status(token, 'ok', 200)
                return data.get("items", []), token
            if resp.status_code in (403, 429):
                mark_token_status(token, 'rate_limited', resp.status_code)
                log_message(f"GitHub限流/拒绝: {resp.status_code}，更换token重试", "warning")
                continue
            else:
                mark_token_status(token, 'error', resp.status_code)
                log_message(f"GitHub API 错误: {resp.status_code}", "error")
        except Exception as e:
            mark_token_status(token, 'error', -1)
            log_message(f"搜索失败: {str(e)}", "error")
    return [], None

            if resp.status_code == 200:
                data = resp.json()
# 扫描趋势：每分钟累计快照（持久化）

def record_scan_trend(delta: int):
    try:
        now_min = datetime.now().strftime('%Y-%m-%d %H:%M')
        trend = _config_get('scan_trend', {}) or {}
        cur = int(trend.get(now_min, 0))
        trend[now_min] = cur + max(0, int(delta))
        _config_set('scan_trend', trend)
    except Exception:
        pass

                return data.get("items", []), token
            # 速率限制或权限问题 => 尝试下一个token
            if resp.status_code in (403, 429):
                log_message(f"GitHub限流/拒绝: {resp.status_code}，更换token重试", "warning")
                continue
            else:
                log_message(f"GitHub API 错误: {resp.status_code}", "error")
        except Exception as e:
            log_message(f"搜索失败: {str(e)}", "error")
    return [], None


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

# 提取 OpenRouter Keys（兼容旧调用，内部走模式）
def extract_openrouter_keys(content: str) -> List[str]:
    pattern = r'(sk-or-[A-Za-z0-9\-_]{20,60})'
    return list(set(re.findall(pattern, content)))

# 路径黑名单判断
def is_blacklisted_path(path: str) -> bool:
    bl = config.get('path_blacklist') or []
    p = (path or '').lower()
    return any(token in p for token in bl)

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
            (key_value, key_type, balance, limit_amount, is_free_tier, source_repo, source_url, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            key,
            info.get('type', 'openrouter'),
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

            # 使用任意可用token执行搜索（带轮换和限流处理）
            results, used_token = search_github_any(query)
            if not results:
                continue

                for item in results[:config['max_results_per_query']]:
                    if not scanner_running:
                        break

                    # 路径黑名单过滤
                    if is_blacklisted_path(item.get('path') or ''):
                        continue

                    # 获取文件内容（沿用用于搜索的 used_token 不必，但这里走匿名raw）
                    content = get_file_content(item, used_token or '')
                    if not content:
                        continue

                    # 提取多厂商 keys
                    keys_by = extract_keys_by_provider(content)

                    # 统计扫描到的密钥数量（提取到多少个就记多少个）
                    total_found = sum(len(v) for v in keys_by.values())
                    if total_found:
                        inc_counter('scanned_keys_total', total_found)
                        record_scan_trend(total_found)

                    # OpenRouter 验证与保存
                    for key in keys_by.get('openrouter', []):
                        info = validate_openrouter_key(key)
                        info['type'] = 'openrouter'
                        if info.get('valid'):
                            log_message(f"✅ [OpenRouter] 有效: {key[:10]}...，使用量: ${info.get('balance',0)}", "success")
                            save_key(key, info, {
                                'repo': item['repository']['full_name'],
                                'url': item['html_url']
                            })
                        else:
                            log_message(f"❌ [OpenRouter] 无效: {key[:10]}...", "warning")

                    # 其他厂商：执行验证并保存有效的
                    for key in keys_by.get('openai', []):
                        info = validate_openai_key(key)
                        if info.get('valid'):
                            log_message(f"✅ [OpenAI] 有效: {key[:10]}...", "success")
                            save_key(key, {**info, 'balance': 0, 'limit': 0, 'is_free_tier': False}, {
                                'repo': item['repository']['full_name'], 'url': item['html_url']
                            })
                        else:
                            log_message(f"❌ [OpenAI] 无效: {key[:10]}...", "warning")

                    for key in keys_by.get('anthropic', []):
                        info = validate_anthropic_key(key)
                        if info.get('valid'):
                            log_message(f"✅ [Anthropic] 有效: {key[:10]}...", "success")
                            save_key(key, {**info, 'balance': 0, 'limit': 0, 'is_free_tier': False}, {
                                'repo': item['repository']['full_name'], 'url': item['html_url']
                            })
                        else:
                            log_message(f"❌ [Anthropic] 无效: {key[:10]}...", "warning")

                    for key in keys_by.get('gemini', []):
                        info = validate_gemini_key(key)
                        if info.get('valid'):
                            log_message(f"✅ [Gemini] 有效: {key[:10]}...", "success")
                            save_key(key, {**info, 'balance': 0, 'limit': 0, 'is_free_tier': False}, {
                                'repo': item['repository']['full_name'], 'url': item['html_url']
                            })
                        else:
                            log_message(f"❌ [Gemini] 无效: {key[:10]}...", "warning")

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
    global scanner_start_time
    scanner_start_time = datetime.now()
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
        SELECT key_value, key_type, balance, limit_amount, is_free_tier, source_repo, source_url, found_at, last_checked
        FROM keys
        ORDER BY found_at DESC
    """)

    keys = []
    for row in c.fetchall():
        keys.append({
            'key': row[0],
            'type': row[1],
            'key_display': row[0][:15] + '...' + row[0][-5:],
            'balance': row[2],
            'limit': row[3],
            'is_free_tier': row[4],
            'source_repo': row[5],
            'source_url': row[6],
            'found_at': row[7],
            'last_checked': row[8]
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
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """返回分组统计和累计扫描数量"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT key_type, COUNT(*) FROM keys GROUP BY key_type")
    by_type = {row[0] or 'unknown': row[1] for row in c.fetchall()}
    c.execute("SELECT SUM(COALESCE(balance,0)) FROM keys WHERE key_type='openrouter'")
    or_usage = c.fetchone()[0] or 0
    conn.close()

    # Token 状态统计
    tokens = [t.strip() for t in (config.get('github_tokens') or []) if t.strip()]
    status_vals = [token_status.get(t, {}).get('status', 'unknown') for t in tokens]
    ok = sum(1 for s in status_vals if s == 'ok')
    rate_limited = sum(1 for s in status_vals if s == 'rate_limited')

    # 扫描趋势（仅最近24小时）
    trend_all = _config_get('scan_trend', {}) or {}
    cutoff = datetime.now() - timedelta(hours=24)
    trend = {}
    for k, v in trend_all.items():
        try:
            if datetime.strptime(k, '%Y-%m-%d %H:%M') >= cutoff:
                trend[k] = v
        except Exception:
            continue

    # 运行时间
    app_uptime_s = int((datetime.now() - app_start_time).total_seconds())
    scan_uptime_s = int((datetime.now() - scanner_start_time).total_seconds()) if (scanner_start_time and scanner_running) else 0

    # 扫描速率（keys/min）：最近10分钟平均
    try:
        sorted_keys = sorted(trend.keys())
        window = sorted_keys[-10:] if len(sorted_keys) >= 10 else sorted_keys
        total_in_window = sum(trend[k] for k in window) if window else 0
        scan_rate_kpm = round(total_in_window / max(1, len(window)), 2)
    except Exception:
        scan_rate_kpm = 0.0

    return jsonify({
        'running': scanner_running,
        'by_type': by_type,
        'openrouter_usage_total': or_usage,
        'scanned_keys_total': get_counter('scanned_keys_total', 0),
        'tokens_total': len(tokens),
        'tokens_ok': ok,
        'tokens_rate_limited': rate_limited,
        'scan_trend': trend,
        'app_uptime_s': app_uptime_s,
        'scan_uptime_s': scan_uptime_s,
        'scan_rate_kpm': scan_rate_kpm,
    })

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