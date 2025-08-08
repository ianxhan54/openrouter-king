#!/usr/bin/env python3
"""将用户提供的有效Gemini密钥添加到数据库"""

import sqlite3
from datetime import datetime
import time
import requests

def validate_gemini_key(kv: str) -> int:
    """验证Gemini密钥"""
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={kv}'
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        'contents': [{'parts': [{'text': 'test'}]}],
        'generationConfig': {'maxOutputTokens': 1, 'temperature': 0}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if 'candidates' in data:
                return 200
        return response.status_code
    except:
        return -1

# 用户提供的密钥
user_keys = """AIzaSyCETBi_6UT5zVuu6JvjcuQU4l8IiPHCxxM
AIzaSyBBTNFznyQOKaD56pYb-dXxwbp8bGYOXAI
AIzaSyCZElVwB4zgBuV0Fgh2CSb7V_NN-AXX4BI
AIzaSyB8hSdTnxtL8SpnJcgRNQIKQlM1R7tLMT4
AIzaSyCAK7veu4k9hT88E0pUrSPbmILs0vPfLtI
AIzaSyBDwngcSoX_SZaHhSz_sQmVw7a66f6krn4
AIzaSyAHTSDawDuH4CSzi_nGm5Ls_C-_uoDYtpg
AIzaSyBxyaIX6Ot8-9ii09iY9xj92XYSdixzkDk
AIzaSyAfuZemSzE8SfcEwhCqPWsu1QXl7DQtl3g
AIzaSyDnGJZU-RoCH2j2ZU-hA6jkGzEk0-YTSIk""".split('\n')

print("Adding user-provided Gemini keys to database...")
print("=" * 60)

conn = sqlite3.connect('app.db')
c = conn.cursor()

added = 0
updated = 0
for i, key in enumerate(user_keys[:10], 1):  # 只处理前10个避免触发限制
    key = key.strip()
    if not key:
        continue
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 检查密钥是否已存在
    c.execute("SELECT key_value, status FROM keys WHERE key_value=?", (key,))
    existing = c.fetchone()
    
    if existing:
        print(f"Key #{i}: {key[:20]}... already exists (status: {existing[1]})")
        # 更新验证状态
        status = validate_gemini_key(key)
        c.execute("UPDATE keys SET status=?, last_checked=? WHERE key_value=?", 
                  (str(status), now, key))
        updated += 1
        print(f"  Updated status to: {status}")
    else:
        print(f"Key #{i}: {key[:20]}... adding to database")
        # 插入新密钥
        c.execute("INSERT INTO keys (key_value, key_type, status, found_at, last_checked, balance) VALUES (?,?,?,?,?,?)",
                  (key, 'gemini', None, now, None, 0))
        added += 1
        
        # 验证密钥
        time.sleep(0.5)  # 避免过快
        status = validate_gemini_key(key)
        c.execute("UPDATE keys SET status=?, last_checked=? WHERE key_value=?", 
                  (str(status), now, key))
        print(f"  Validation status: {status}")
    
    conn.commit()
    time.sleep(0.5)  # 避免触发限制

conn.close()

print("\n" + "=" * 60)
print(f"Complete! Added: {added}, Updated: {updated}")