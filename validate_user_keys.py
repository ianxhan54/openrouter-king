#!/usr/bin/env python3
"""验证用户提供的Gemini密钥"""

import requests
import time

def validate_gemini_key(key):
    """验证单个Gemini密钥"""
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={key}'
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    payload = {
        'contents': [{
            'parts': [{'text': 'test'}]
        }],
        'generationConfig': {
            'maxOutputTokens': 1
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        return response.status_code
    except Exception as e:
        return -1

# 用户提供的密钥列表
user_keys = """AIzaSyCETBi_6UT5zVuu6JvjcuQU4l8IiPHCxxM
AIzaSyBBTNFznyQOKaD56pYb-dXxwbp8bGYOXAI
AIzaSyCZElVwB4zgBuV0Fgh2CSb7V_NN-AXX4BI
AIzaSyB8hSdTnxtL8SpnJcgRNQIKQlM1R7tLMT4
AIzaSyCAK7veu4k9hT88E0pUrSPbmILs0vPfLtI""".split('\n')

print("验证用户提供的Gemini密钥...")
print("=" * 60)

valid_count = 0
invalid_count = 0
rate_limited_count = 0

for i, key in enumerate(user_keys[:5], 1):  # 只测试前5个避免触发限制
    key = key.strip()
    if not key:
        continue
    
    print(f"\n测试密钥 #{i}: {key[:20]}...")
    status = validate_gemini_key(key)
    
    if status == 200:
        print(f"  [VALID] Status: {status}")
        valid_count += 1
    elif status == 429:
        print(f"  [RATE LIMITED] Status: {status}")
        rate_limited_count += 1
    else:
        print(f"  [INVALID] Status: {status}")
        invalid_count += 1
    
    # 避免请求过快
    time.sleep(1)

print("\n" + "=" * 60)
print(f"测试结果汇总:")
print(f"  有效密钥: {valid_count}")
print(f"  无效密钥: {invalid_count}")
print(f"  被限流密钥: {rate_limited_count}")
print(f"  总计测试: {valid_count + invalid_count + rate_limited_count}")