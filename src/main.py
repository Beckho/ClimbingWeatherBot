"""
클라이밍 날씨 TGTWTG 봇 - 메인 프로그램
여러 기상 API를 통합하여 주말 야외 클라이밍 적합도를 분석하고,
텔레그램 메시지로 전송합니다.
"""
import sys
from pathlib import Path

# Windows asyncio 정책 설정 (필수)
if sys.platform == 'win32':
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except:
        pass

import logging

# 프로젝트 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from telegram_bot import ClimbingWeatherBot
from scheduler import WeatherScheduler
from weather_api import refresh_all_sites_cache

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    logger.info("=" * 50)
    logger.info("클라이밍 날씨 TGTWTG 봇 시작")
    logger.info("=" * 50)
    
    # 설정 유효성 확인
    if not Config.validate():
        logger.error("설정 검증 실패. .env 파일을 확인하세요.")
        return False
    
    logger.info("[OK] 설정 검증 완료")
    
    # 사이트 설정 로드
    sites_config = Config.load_sites()
    if not sites_config:
        logger.error("클라이밍 지역 설정을 로드할 수 없습니다.")
        return False
    
    logger.info(f"[OK] {len(sites_config['sites'])}개 클라이밍 지역 로드 완료")
    
    # 텔레그램 봇 생성
    try:
        bot = ClimbingWeatherBot(Config.TELEGRAM_BOT_TOKEN)
        logger.info("[OK] 텔레그램 봇 생성 완료")
    except Exception as e:
        logger.error(f"봇 생성 실패: {e}")
        return False
    
    # 봇 실행
    try:
        logger.info("-" * 50)
        logger.info("텔레그램 봇 시작...")
        logger.info("명령어: /start, /weather, /weekend, /sites, /help")
        logger.info("텔레그램에서 봇과 대화를 시작하세요.")
        logger.info("Ctrl+C로 종료합니다.")
        logger.info("-" * 50)

        sites = sites_config['sites']

        async def post_init(application):
            # 스케줄러 시작
            scheduler = WeatherScheduler(bot)
            scheduler.add_morning_report(Config.SCHEDULE_HOUR, Config.SCHEDULE_MINUTE)
            scheduler.add_cache_refresh(sites, Config.OPENWEATHER_API_KEY, Config.KMA_API_KEY)
            scheduler.start()
            logger.info("[OK] 스케줄러 시작 (아침 리포트 + 30분 캐시 갱신)")

            # 초기 캐시 워밍업 (백그라운드)
            import asyncio as _asyncio
            loop = _asyncio.get_event_loop()
            loop.run_in_executor(
                None, refresh_all_sites_cache,
                sites, Config.OPENWEATHER_API_KEY, Config.KMA_API_KEY
            )
            logger.info("[OK] 초기 캐시 워밍업 시작")

        # run_polling()은 PTB v20에서 내부적으로 이벤트 루프를 관리하는 동기 메서드
        app = bot.create_application(post_init=post_init)
        app.run_polling()
        
    except KeyboardInterrupt:
        logger.info("\n프로그램 종료됨 (사용자 중단)")
        return True
    except Exception as e:
        logger.error(f"봇 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == '__main__':
    logger.info("Python 클라이밍 날씨 봇 초기화...")
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("프로그램 종료")
        sys.exit(0)
