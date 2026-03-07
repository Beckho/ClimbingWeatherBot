#!/usr/bin/env python
"""
봇 토큰 유효성 테스트
"""
import sys
import os
sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), 'src')))
os.chdir(os.path.dirname(__file__))

import requests
from config import Config

token = Config.TELEGRAM_BOT_TOKEN
print(f"테스트 중인 봇 토큰: {token}")

# getMe 호출로 토큰 확인
url = f"https://api.telegram.org/bot{token}/getMe"

try:
    response = requests.get(url, timeout=5)
    data = response.json()
    
    print("\n" + "="*60)
    print("✅ 봇 토큰이 유효합니다!")
    print("="*60)
    print(f"봇 ID: {data.get('result', {}).get('id')}")
    print(f"봇 이름: {data.get('result', {}).get('first_name')}")
    print(f"봇 username: @{data.get('result', {}).get('username')}")
    print("="*60)
    print("\n위의 봇 이름이 정말로 당신이 사용할 봇이 맞는지 확인하세요!")
    print(f"https://t.me/{data.get('result', {}).get('username')} 에 방문하세요")
    
except Exception as e:
    print(f"\n❌ 오류: {e}")
    print("봇 토큰이 유효하지 않을 수 있습니다.")
