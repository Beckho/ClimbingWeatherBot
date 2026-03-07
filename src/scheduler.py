"""
스케줄 관리 모듈
매일 아침 자동으로 날씨 리포트 발송
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

logger = logging.getLogger(__name__)


class WeatherScheduler:
    """날씨 리포트 스케줄 관리"""
    
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
    
    def add_morning_report(self, hour: int = 7, minute: int = 0) -> None:
        """아침 날씨 리포트 스케줄 추가"""
        self.scheduler.add_job(
            self.bot.send_morning_report,
            trigger=CronTrigger(hour=hour, minute=minute),
            id='morning_report',
            name='일일 아침 날씨 리포트',
            replace_existing=True
        )
        logger.info(f"아침 리포트 스케줄 설정: 매일 {hour:02d}:{minute:02d}")
    
    def start(self) -> None:
        """스케줄러 시작"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("스케줄러 시작됨")
    
    def shutdown(self) -> None:
        """스케줄러 종료"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("스케줄러 종료됨")
    
    def get_jobs(self) -> list:
        """현재 등록된 작업 목록"""
        return self.scheduler.get_jobs()
    
    def list_jobs(self) -> None:
        """작업 목록 출력"""
        jobs = self.get_jobs()
        if jobs:
            print(f"\n등록된 작업 ({len(jobs)}개):")
            for job in jobs:
                print(f"  - {job.name}: {job.trigger}")
        else:
            print("등록된 작업이 없습니다.")


async def test_scheduler():
    """스케줄러 테스트"""
    from telegram_bot import ClimbingWeatherBot
    from config import Config
    
    bot = ClimbingWeatherBot(Config.TELEGRAM_BOT_TOKEN)
    scheduler = WeatherScheduler(bot)
    
    # 테스트를 위해 1분 후로 설정
    scheduler.add_morning_report(hour=6, minute=0)
    scheduler.start()
    
    scheduler.list_jobs()
    
    # 스케줄러 실행 (테스트)
    try:
        while True:
            import asyncio
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == '__main__':
    import asyncio
    asyncio.run(test_scheduler())
