#!/usr/bin/env python3
"""
Gemini密钥重新验证脚本
修复误判为有效的Gemini密钥
"""

import sqlite3
import os
import requests
import time
from datetime import datetime

def _validate_gemini_key_real(kv: str) -> int:
    """使用实际生成API验证Gemini密钥"""
    
    # 使用 generateContent API 进行真实验证
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={kv}'
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    # 最小化的测试请求
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
        
        # 检查HTTP状态码
        if response.status_code != 200:
            return response.status_code
        
        # 检查响应内容是否包含错误
        try:
            data = response.json()
            # 如果有error字段，说明密钥无效
            if 'error' in data:
                error_code = data.get('error', {}).get('code', 403)
                return error_code
            # 如果有candidates字段，说明成功
            elif 'candidates' in data:
                return 200
            else:
                return 403  # 未知响应格式，视为无效
        except:
            return 403  # JSON解析失败，视为无效
            
    except Exception as e:
        print(f"   验证异常: {str(e)}")
        return -1

def main():
    DB_PATH = os.path.join(os.path.dirname(__file__), 'app.db')
    
    if not os.path.exists(DB_PATH):
        print("❌ 找不到数据库文件 app.db")
        return
    
    print("🔍 Gemini密钥重新验证脚本")
    print("=" * 40)
    
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 获取所有状态为200的Gemini密钥
    c.execute("SELECT key_value, status FROM keys WHERE key_type='gemini' AND status='200'")
    gemini_keys = c.fetchall()
    
    if not gemini_keys:
        print("✅ 没有找到状态为200的Gemini密钥")
        conn.close()
        return
    
    print(f"🔍 找到 {len(gemini_keys)} 个状态为200的Gemini密钥")
    print(f"⚠️  正在重新验证...")
    
    corrected = 0
    still_valid = 0
    
    for i, (key_value, old_status) in enumerate(gemini_keys, 1):
        print(f"\n[{i}/{len(gemini_keys)}] 验证: {key_value[:20]}...")
        
        # 重新验证
        new_status = _validate_gemini_key_real(key_value)
        
        if new_status != 200:
            # 密钥确实无效，更新数据库
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("UPDATE keys SET status=?, last_checked=? WHERE key_value=?", 
                     (str(new_status), now, key_value))
            corrected += 1
            print(f"   ❌ 已修正: 200 → {new_status}")
        else:
            still_valid += 1
            print(f"   ✅ 确实有效")
        
        # 避免请求过快
        time.sleep(1)
    
    # 提交更改
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 40)
    print("🎯 验证结果:")
    print(f"   总数: {len(gemini_keys)}")
    print(f"   仍然有效: {still_valid}")
    print(f"   已修正: {corrected}")
    
    if corrected > 0:
        print(f"\n✅ 已修正 {corrected} 个误判的Gemini密钥")
        print("   建议重启应用以生效新的验证逻辑")
    else:
        print(f"\n🎉 所有Gemini密钥状态都是正确的")

if __name__ == '__main__':
    main()