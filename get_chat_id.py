#!/usr/bin/env python
"""
Chat ID 로깅 추가 버전
메시지가 도착하면 Chat ID를 즉시 터미널에 출력합니다.
"""
import sys
import os
from pathlib import Path

# Windows asyncio 정책 설정 (필수)
if sys.platform == 'win32':
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except:
        pass

import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import logging

sys.path.insert(0, str(Path(__file__).parent / 'src'))
os.chdir(Path(__file__).parent)

from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Chat ID 추출 및 출력"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or "없음"
    
    logger.info("=" * 50)
    logger.info(f"메시지 수신!")
    logger.info(f"Chat ID: {chat_id}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Username: @{username}")
    logger.info("=" * 50)
    logger.info(".env 파일의 TELEGRAM_CHAT_ID를 위 값으로 변경하세요!")
    logger.info("=" * 50)
    
    await update.message.reply_text(
        f"Chat ID가 터미널에 출력되었습니다!\n\n"
        f"Chat ID: `{chat_id}`를 .env 파일에 입력하세요."
    )

async def main():
    """Chat ID 추출용 봇 실행"""
    logger.info("Chat ID 확인용 봇 시작...")
    logger.info("이 봇에 아무 메시지나 보내면 Chat ID가 출력됩니다!")
    
    app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # 모든 메시지 처리
    app.add_handler(
        MessageHandler(filters.TEXT, get_chat_id)
    )
    
    await app.run_polling()

if __name__ == '__main__':
    if sys.platform == 'win32':
        import asyncio
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except:
            pass
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("종료됨")
