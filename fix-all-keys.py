#!/usr/bin/env python3
"""
所有模型密钥重新验证脚本
使用新的实际API验证方法修复误判的密钥
"""

import sqlite3
import os
import requests
import time
from datetime import datetime

def _validate_openai_key_real(kv: str) -> int:
    """使用实际聊天API验证OpenAI密钥"""
    headers = {
        'Authorization': f'Bearer {kv}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': 'gpt-3.5-turbo',
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
        
        if response.status_code == 200:
            return 200
        elif response.status_code == 401:
            return 401
        elif response.status_code == 429:
            return 429
        elif response.status_code == 403:
            return 403
        else:
            return response.status_code
    except Exception as e:
        print(f"   验证异常: {str(e)}")
        return -1

def _validate_anthropic_key_real(kv: str) -> int:
    """使用实际消息API验证Anthropic密钥"""
    headers = {
        'x-api-key': kv,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json'
    }
    
    payload = {
        'model': 'claude-3-haiku-20240307',
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
        
        if response.status_code == 200:
            try:
                data = response.json()
                if 'content' in data and data.get('content'):
                    return 200
                else:
                    return 403
            except:
                return 403
        elif response.status_code == 401:
            return 401
        elif response.status_code == 429:
            return 429
        elif response.status_code == 403:
            return 403
        else:
            return response.status_code
    except Exception as e:
        print(f"   验证异常: {str(e)}")
        return -1

def _validate_gemini_key_real(kv: str) -> int:
    """使用实际生成API验证Gemini密钥"""
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={kv}'
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    payload = {
        'contents': [{
            'parts': [{'text': 'hi'}]
        }],
        'generationConfig': {
            'maxOutputTokens': 1
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code != 200:
            return response.status_code
        
        try:
            data = response.json()
            if 'error' in data:
                error_code = data.get('error', {}).get('code', 403)
                return error_code
            elif 'candidates' in data:
                return 200
            else:
                return 403
        except:
            return 403
    except Exception as e:
        print(f"   验证异常: {str(e)}")
        return -1

def _validate_openrouter_key_real(kv: str) -> int:
    """使用实际聊天API验证OpenRouter密钥"""
    headers = {
        'Authorization': f'Bearer {kv}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com',
        'X-Title': 'Key Validation Test'
    }
    
    payload = {
        'model': 'meta-llama/llama-3.2-1b-instruct:free',
        'messages': [{'role': 'user', 'content': 'hi'}],
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
    except Exception as e:
        print(f"   验证异常: {str(e)}")
        return -1

def main():
    DB_PATH = os.path.join(os.path.dirname(__file__), 'app.db')
    
    if not os.path.exists(DB_PATH):
        print("❌ 找不到数据库文件 app.db")
        return
    
    print("🔍 所有模型密钥重新验证脚本")
    print("=" * 50)
    
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 验证函数映射
    validators = {
        'openai': _validate_openai_key_real,
        'anthropic': _validate_anthropic_key_real,
        'gemini': _validate_gemini_key_real,
        'openrouter': _validate_openrouter_key_real
    }
    
    total_corrected = 0
    total_checked = 0
    
    for key_type, validator in validators.items():
        print(f"\n🔍 检查 {key_type.upper()} 密钥...")
        
        # 获取所有状态为200的密钥
        c.execute("SELECT key_value, status FROM keys WHERE key_type=? AND status='200'", (key_type,))
        keys = c.fetchall()
        
        if not keys:
            print(f"   ✅ 没有找到状态为200的{key_type}密钥")
            continue
        
        print(f"   📊 找到 {len(keys)} 个状态为200的密钥，开始验证...")
        
        corrected = 0
        still_valid = 0
        
        for i, (key_value, old_status) in enumerate(keys, 1):
            print(f"   [{i}/{len(keys)}] 验证: {key_value[:20]}...")
            
            # 重新验证
            new_status = validator(key_value)
            total_checked += 1
            
            if new_status != 200:
                # 密钥确实无效，更新数据库
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                c.execute("UPDATE keys SET status=?, last_checked=? WHERE key_value=?", 
                         (str(new_status), now, key_value))
                corrected += 1
                total_corrected += 1
                print(f"      ❌ 已修正: 200 → {new_status}")
            else:
                still_valid += 1
                print(f"      ✅ 确实有效")
            
            # 避免请求过快
            time.sleep(1.5)
        
        print(f"   📊 {key_type.upper()} 结果: 总数={len(keys)}, 仍有效={still_valid}, 已修正={corrected}")
    
    # 提交更改
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("🎯 总体验证结果:")
    print(f"   检查密钥总数: {total_checked}")
    print(f"   修正误判密钥: {total_corrected}")
    
    if total_corrected > 0:
        print(f"\n✅ 已修正 {total_corrected} 个误判密钥")
        print("   建议重启应用以使用新的验证逻辑")
    else:
        print(f"\n🎉 所有密钥状态都是正确的")

if __name__ == '__main__':
    main()