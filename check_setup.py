#!/usr/bin/env python
"""프로젝트 설정 검증 스크립트"""
import sys
from pathlib import Path

# src 디렉토리를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from config import Config
    print("✓ 모듈 로드 성공")
    
    # 환경 변수 검증
    print("\n=== 설정 검증 ===")
    if Config.TELEGRAM_BOT_TOKEN:
        print("✓ TELEGRAM_BOT_TOKEN 설정됨")
    else:
        print("⚠ TELEGRAM_BOT_TOKEN 미설정 (필수)")
    
    if Config.TELEGRAM_CHAT_ID:
        print("✓ TELEGRAM_CHAT_ID 설정됨")
    else:
        print("⚠ TELEGRAM_CHAT_ID 미설정 (필수)")
    
    if Config.OPENWEATHER_API_KEY:
        print("✓ OPENWEATHER_API_KEY 설정됨")
    else:
        print("⚠ OPENWEATHER_API_KEY 미설정 (필수)")
    
    # 사이트 설정 로드
    sites = Config.load_sites()
    if sites:
        print(f"✓ 클라이밍 지역 {len(sites['sites'])}개 로드 완료")
    
    print("\n=== 의존성 확인 ===")
    import json
    import requests
    from telegram import Update
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    print("✓ 모든 의존성 로드 완료")
    
    print("\n✅ 설정 완료!")
    print("\n다음 단계:")
    print("1. .env.example을 .env로 복사")
    print("2. API 키 설정")
    print("3. python src/main.py 실행")
    
except Exception as e:
    print(f"❌ 오류: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
