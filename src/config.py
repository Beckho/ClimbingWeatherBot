"""
설정 관리 모듈
"""
import os
import json
import logging
from dotenv import load_dotenv
from pathlib import Path

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/weather_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Config:
    """애플리케이션 설정"""
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Weather APIs
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
    KMA_API_KEY = os.getenv('KMA_API_KEY', '')
    
    # Scheduler
    SCHEDULE_HOUR = int(os.getenv('SCHEDULE_HOUR', 7))
    SCHEDULE_MINUTE = int(os.getenv('SCHEDULE_MINUTE', 0))
    
    # Sites config
    CLIMBING_SITES_CONFIG = os.getenv('CLIMBING_SITES_CONFIG', 'config/sites.json')
    
    @staticmethod
    def load_sites():
        """클라이밍 지역 설정 로드"""
        try:
            with open(Config.CLIMBING_SITES_CONFIG, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"설정 로드 완료: {len(data['sites'])}개 지역")
            return data
        except FileNotFoundError:
            logger.error(f"설정 파일을 찾을 수 없습니다: {Config.CLIMBING_SITES_CONFIG}")
            return None
        except json.JSONDecodeError:
            logger.error("JSON 파싱 오류")
            return None
    
    @staticmethod
    def validate():
        """설정 유효성 확인"""
        errors = []
        
        if not Config.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다")
        if not Config.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID가 설정되지 않았습니다")
        if not Config.OPENWEATHER_API_KEY and not Config.KMA_API_KEY:
            errors.append("최소 하나의 기상 API 키가 필요합니다")
        
        if errors:
            logger.error("설정 오류:\n" + "\n".join(errors))
            return False
        return True


if __name__ == '__main__':
    Config.validate()
    sites = Config.load_sites()
    if sites:
        print(f"로드된 클라이밍 지역 수: {len(sites['sites'])}")
