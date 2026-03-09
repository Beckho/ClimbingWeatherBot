"""
텔레그램 봇 구현 모듈
메시지 수신 및 날씨 알림 발송
"""
import logging
import unicodedata
from typing import Optional, Dict
from telegram import Update, User
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from datetime import datetime
import json

from weather_api import get_weekend_forecast
from analyzer import WeatherAnalyzer
from config import Config

logger = logging.getLogger(__name__)


class ClimbingWeatherBot:
    """클라이밍 날씨 봇 클래스"""
    
    def __init__(self, token: str):
        self.token = token
        self.application = None
        self.sites_config = Config.load_sites()
        self.sites = {site['name']: site for site in self.sites_config['sites']} if self.sites_config else {}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """시작 명령어"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        logger.info(f"사용자 시작: {user.id} - {user.username} (chat_id={chat_id})")

        admin_ids = [cid.strip() for cid in Config.TELEGRAM_CHAT_ID.split(',') if cid.strip()]
        is_admin = str(chat_id) in admin_ids

        subscribe_notice = "" if is_admin else """
🔔 *매일 아침 자동 예보 알림 설정 안내*
알림 설정 신청이 관리자에게 자동으로 전달되었습니다.
관리자가 확인 후 알림을 추가해 드릴 예정입니다."""

        welcome_message = f"""
안녕하세요! 🏔️ *클라이밍 날씨 TGTWTG 봇*입니다.

이 봇은 주말 야외 클라이밍에 최적의 날씨 정보를 제공합니다.
매일 아침 자동으로 주말 예보를 받아보실 수 있습니다.

🔹 *사용 가능한 명령어 or 클릭:*
/start - 봇 정보 및 도움말
/weather - 지금 바로 날씨 조회
/weekend - 주말 날씨 예보
/sites - 등록된 클라이밍 지역 목록
/unsubscribe - 자동 예보 알림 해제
/help - 상세 도움말
{subscribe_notice}
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')

        # 관리자(첫 번째 TELEGRAM_CHAT_ID)에게 새 사용자 알림
        if admin_ids and not is_admin:
            admin_id = admin_ids[0]
            try:
                username_str = f"@{user.username}" if user.username else "(없음)"
                name_str = user.full_name or user.first_name or "?"
                notify_msg = (
                    f"🔔 *새 사용자가 봇을 시작했습니다*\n\n"
                    f"이름: {name_str}\n"
                    f"유저명: {username_str}\n"
                    f"Chat ID: `{chat_id}`\n\n"
                    f"알림 설정 추가 시 TELEGRAM\\_CHAT\\_ID에 이 Chat ID를 추가하세요."
                )
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=notify_msg,
                    parse_mode='Markdown'
                )
                logger.info(f"관리자({admin_id})에게 새 사용자 알림 전송 완료")
            except Exception as e:
                logger.error(f"관리자 알림 전송 실패: {e}")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """도움말"""
        help_message = """
📖 *사용 가이드*

🌤️ **날씨 조회 방법:**
1. /weather - 현재 모든 지역 날씨 조회
2. /weekend - 이번 주말 날씨 예보 (표 형식)
3. /sites - 등록된 모든 지역의 상세 정보
4. /help - 이 도움말

🏔️ **모니터링 지역 (13개)**

*스포츠 클라이밍 (7개)*
• 간현(원주) • 조비산(용인) • 선운산(고창)
• 삼성산(안양) • 삼천바위(완주)
• 연경(대구) • 새벽암장(파주)

*볼더링 (6개)*
• 진안(진안) • 무등산(광주) • 북한산(서울)
• 불암산(노원) • 감자바위(안양) • 을왕리(인천)

💬 **자연스러운 말로도 사용 가능:**
"간현 날씨 어때?", "주말은?", "지역 뭐가 있어?" 등

📍 **주말 예보 표 형식:**
최저~최고 온도와 날씨 아이콘으로 표시
☀️ 맑음, ☁️ 흐림, 🌧️ 비, ❄️ 눈, ⛈️ 뇌우, 🌫️ 안개

🔔 **자동 알림:**
매일 아침 9시에 자동으로 주말 예보 발송

        """
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def sites_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """등록된 클라이밍 지역 목록"""
        if not self.sites:
            await update.message.reply_text("등록된 지역이 없습니다.")
            return
        
        message = "🏔️ *등록된 클라이밍 지역:*\n\n"
        for i, (name, site) in enumerate(self.sites.items(), 1):
            message += f"{i}. {name}\n"
            message += f"   위치: {site['region']}\n"
            message += f"   좌표: ({site['latitude']}, {site['longitude']})\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """현재 날씨 조회"""
        if not Config.OPENWEATHER_API_KEY:
            await update.message.reply_text(
                "⚠️ API 키가 설정되지 않았습니다. .env 파일을 확인하세요."
            )
            return
        
        await update.message.reply_text("🔄 날씨 정보를 조회 중입니다...")
        
        try:
            messages = []
            for site_name, site in self.sites.items():
                forecast = self._get_site_weather(
                    site_name, 
                    site['latitude'], 
                    site['longitude']
                )
                if forecast:
                    messages.append(forecast)
            
            if messages:
                for msg in messages:
                    await update.message.reply_text(msg, parse_mode='Markdown')
            else:
                await update.message.reply_text("날씨 정보를 불러올 수 없습니다.")
        except Exception as e:
            logger.error(f"날씨 조회 오류: {e}")
            await update.message.reply_text(f"오류가 발생했습니다: {str(e)}")
    
    async def weekend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """주말 날씨 예보 - 표 형식으로 모든 지역 통합"""
        if not Config.OPENWEATHER_API_KEY:
            await update.message.reply_text(
                "⚠️ API 키가 설정되지 않았습니다."
            )
            return
        
        await update.message.reply_text("🔄 주말 예보를 분석 중입니다...")
        
        try:
            # 모든 지역의 주말 예보 병렬 수집
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def fetch(site_name, site):
                return site_name, get_weekend_forecast(
                    site['latitude'],
                    site['longitude'],
                    Config.OPENWEATHER_API_KEY,
                    Config.KMA_API_KEY,
                    site.get('region')
                )

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                tasks = [
                    loop.run_in_executor(executor, fetch, name, site)
                    for name, site in self.sites.items()
                ]
                results = await asyncio.gather(*tasks)

            all_forecasts = {name: forecast for name, forecast in results}
            
            # 표 형식 메시지 생성
            message = self._format_all_weekend_forecasts(all_forecasts)
            
            if message:
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text("주말 예보를 불러올 수 없습니다.")
        except Exception as e:
            logger.error(f"주말 예보 조회 오류: {e}")
            await update.message.reply_text(f"오류가 발생했습니다: {str(e)}")
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """일반 메시지 처리"""
        # Chat ID 로깅
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        username = update.effective_user.username or "없음"
        
        logger.info("=" * 60)
        logger.info(f"메시지 수신!")
        logger.info(f"Chat ID: {chat_id}")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Username: @{username}")
        logger.info("=" * 60)
        logger.info(".env 파일의 TELEGRAM_CHAT_ID를 위 Chat ID로 변경하세요!")
        logger.info("=" * 60)
        
        text = update.message.text.lower()
        
        # 주요 키워드 인식
        if any(keyword in text for keyword in ['날씨', '어때', '예보', '조회']):
            await self.weather_command(update, context)
        elif any(keyword in text for keyword in ['주말', '토요일', '일요일']):
            await self.weekend_command(update, context)
        elif any(keyword in text for keyword in ['지역', '목록', '어디', '있는']):
            await self.sites_command(update, context)
        else:
            response = "죄송합니다. 다음 명령어를 사용해주세요:\n"
            response += "/weather - 현재 날씨\n"
            response += "/weekend - 주말 예보\n"
            response += "/sites - 지역 목록\n"
            response += "/help - 도움말"
            await update.message.reply_text(response)
    
    def _get_site_weather(self, site_name: str, lat: float, lon: float) -> Optional[str]:
        """특정 지역의 날씨 정보 조회"""
        try:
            forecast = get_weekend_forecast(lat, lon, Config.OPENWEATHER_API_KEY, Config.KMA_API_KEY)
            
            if not forecast:
                return None
            
            # 소스 확인
            source = forecast.get('source', 'unknown')
            source_emoji = '🔵 기상청' if source == 'kma' else '🟢 OpenWeather'
            
            current = forecast.get('current', {})
            
            weather_message = f"📍 *{site_name}* ({source_emoji})\n"
            weather_message += f"🌡️ 온도: {current.get('temp', 'N/A')}°C\n"
            weather_message += f"💨 바람: {current.get('wind_speed', 'N/A')}m/s\n"
            weather_message += f"💧 습도: {current.get('humidity', 'N/A')}%\n"
            weather_message += f"☁️ 설명: {current.get('description', 'N/A')}\n"
            
            return weather_message
        except Exception as e:
            logger.error(f"날씨 조회 오류 ({site_name}): {e}")
            return None
    
    def _format_weekend_forecast(self, site_name: str, forecast: Dict) -> Optional[str]:
        """주말 예보 포맷팅 (기존 - 사용 안함)"""
        try:
            if not forecast:
                logger.warning(f"[주말 포맷] {site_name} - forecast 데이터 없음")
                return None
            
            if 'openweather' not in forecast:
                logger.warning(f"[주말 포맷] {site_name} - openweather 키 없음. 사용 가능 키: {list(forecast.keys())}")
                return None
            
            data = forecast['openweather']
            
            # 토요일과 일요일 데이터 확인
            saturday = data.get('saturday', [])
            sunday = data.get('sunday', [])
            
            logger.info(f"[주말 포맷] {site_name}: 토요일 {len(saturday)}개, 일요일 {len(sunday)}개 데이터")
            
            # 데이터가 없으면 None 반환
            if not saturday and not sunday:
                logger.warning(f"[주말 포맷] {site_name} - 토요일/일요일 데이터 없음")
                return None
            
            message = f"🗓️ *{site_name}*\n"
            message += f"5일 이내 주말 예보\n\n"
            
            # 토요일
            if saturday:
                message += "*토요일*\n"
                for item in saturday[:3]:  # 처음 3개만
                    timestamp = item.get('timestamp', '')
                    temp = item.get('temp', 'N/A')
                    wind_speed = item.get('wind_speed', 'N/A')
                    description = item.get('description', 'N/A')
                    
                    time_str = timestamp[11:16] if len(timestamp) >= 16 else timestamp
                    message += f"  {time_str} - {temp}°C, 바람{wind_speed}km/h ({description})\n"
                message += "\n"
            else:
                message += "*토요일*: 5일 범위 내 데이터 없음\n\n"
            
            # 일요일
            if sunday:
                message += "*일요일*\n"
                for item in sunday[:3]:  # 처음 3개만
                    timestamp = item.get('timestamp', '')
                    temp = item.get('temp', 'N/A')
                    wind_speed = item.get('wind_speed', 'N/A')
                    description = item.get('description', 'N/A')
                    
                    time_str = timestamp[11:16] if len(timestamp) >= 16 else timestamp
                    message += f"  {time_str} - {temp}°C, 바람{wind_speed}km/h ({description})\n"
            else:
                message += "*일요일*: 5일 범위 내 데이터 없음"
            
            return message
        except Exception as e:
            logger.error(f"[주말 포맷] 예보 포맷팅 오류 ({site_name}): {e}", exc_info=True)
            return None
    
    def _format_all_weekend_forecasts(self, all_forecasts: Dict) -> Optional[str]:
        """모든 지역 주말 예보를 표 형식으로 포맷팅"""
        try:
            import pytz
            from datetime import datetime, timedelta

            # 데이터 수집
            saturday_date = None
            sunday_date = None
            saturday_data = {}
            sunday_data = {}
            next_saturday_data = {}
            next_sunday_data = {}
            data_source = None
            announced_at = None
            has_next_weekend = False

            seoul_tz = pytz.timezone('Asia/Seoul')
            
            # 날씨 설명을 아이콘으로 변환하는 함수
            def get_weather_icon(description):
                """날씨 설명을 아이콘으로 변환"""
                if not description:
                    return "🌤️"
                
                desc_lower = description.lower()
                
                if '맑음' in desc_lower or 'clear' in desc_lower:
                    return "☀️"
                elif '구름' in desc_lower or 'cloud' in desc_lower or '흐림' in desc_lower:
                    return "☁️"
                elif '비' in desc_lower or 'rain' in desc_lower:
                    return "🌧️"
                elif '눈' in desc_lower or 'snow' in desc_lower:
                    return "❄️"
                elif '뇌우' in desc_lower or 'thunderstorm' in desc_lower:
                    return "⛈️"
                elif '안개' in desc_lower or 'mist' in desc_lower or 'fog' in desc_lower:
                    return "🌫️"
                else:
                    return "🌤️"
            
            for site_name, forecast in all_forecasts.items():
                if not forecast:
                    continue

                source = forecast.get('source', 'unknown')
                if data_source is None:
                    data_source = source

                if announced_at is None:
                    announced_at = forecast.get('announced_at')

                if 'next_saturday' in forecast or 'next_sunday' in forecast:
                    has_next_weekend = True

                saturday = forecast.get('saturday', [])
                sunday = forecast.get('sunday', [])
                next_saturday = forecast.get('next_saturday', [])
                next_sunday = forecast.get('next_sunday', [])

                # 토요일 첫 번째 아이템에서 날짜 추출
                if saturday and not saturday_date:
                    ts = saturday[0].get('timestamp', '')
                    try:
                        saturday_date = datetime.fromisoformat(ts).astimezone(seoul_tz).date()
                    except:
                        pass

                # 일요일 첫 번째 아이템에서 날짜 추출
                if sunday and not sunday_date:
                    ts = sunday[0].get('timestamp', '')
                    try:
                        sunday_date = datetime.fromisoformat(ts).astimezone(seoul_tz).date()
                    except:
                        pass

                # 지역별 데이터 저장 (최저/최고 온도, 평균 바람(m/s), 날씨 아이콘)
                def summarize(items):
                    # 중기예보: 날짜당 1개 item, temp_min/max에 실제 최저/최고
                    # 단기예보: 3시간 단위 여러 item, temp_min == temp_max == temp(순간기온)
                    if len(items) == 1:
                        item = items[0]
                        min_temp = item.get('temp_min', item.get('temp', 0))
                        max_temp = item.get('temp_max', item.get('temp', 0))
                    else:
                        temps = [item.get('temp', 0) for item in items]
                        min_temp = min(temps)
                        max_temp = max(temps)
                    avg_wind = sum(item.get('wind_speed', 0) for item in items) / len(items)
                    descriptions = [item.get('description', '') for item in items]
                    icon = get_weather_icon(descriptions[0] if descriptions else '')
                    return (f"{min_temp:.0f}", f"{max_temp:.0f}", avg_wind, icon)

                if saturday:
                    saturday_data[site_name] = summarize(saturday)
                if sunday:
                    sunday_data[site_name] = summarize(sunday)
                if next_saturday:
                    next_saturday_data[site_name] = summarize(next_saturday)
                if next_sunday:
                    next_sunday_data[site_name] = summarize(next_sunday)
            
            logger.info(f"[주말 포맷] sat={len(saturday_data)}, sun={len(sunday_data)}, next_sat={len(next_saturday_data)}, next_sun={len(next_sunday_data)}")

            # 데이터가 전혀 없으면 None 반환
            if not saturday_data and not sunday_data and not next_saturday_data and not next_sunday_data:
                return None

            # 소스 표시
            source_emoji = '🔵 기상청(KMA)' if data_source == 'kma' else '🟢 OpenWeather'
            announced_str = f" | {announced_at} 발표" if announced_at else ""

            # 메시지 구성
            message = f"🗓️ *[ 주말 날씨 예보 ]* ({source_emoji}{announced_str})\n"
            message += "최저/최고 온도 & 평균 풍속 (5일 이내)\n"
            message += "=" * 60 + "\n\n"

            def dw(s):
                """한국어 포함 문자열의 표시 너비 계산 (CJK=2, 기타=1)"""
                w = 0
                for c in s:
                    ea = unicodedata.east_asian_width(c)
                    w += 2 if ea in ('W', 'F') else 1
                return w

            def ljust_dw(s, width):
                """표시 너비 기준으로 왼쪽 정렬"""
                return s + ' ' * max(0, width - dw(s))

            def format_weekend_section(date_obj, date_suffix, data_dict):
                date_str = date_obj.strftime(f"%m-%d ({date_suffix})") if date_obj else f"({date_suffix})"
                sec = f"*📅 {date_str}*\n"
                sec += "```\n"
                COL_NAME = 15  # 삼천바위(완주)(표시너비 14) + 여백 1
                COL_TEMP = 9   # 최대 -5~-2°C (8자)
                COL_WIND = 8   # 최대 10.5m/s (7자)
                sec += ljust_dw("지역", COL_NAME) + ljust_dw("온도", COL_TEMP) + ljust_dw("풍속", COL_WIND) + "날씨 적합\n"
                sec += "-" * (COL_NAME + COL_TEMP + COL_WIND + 2) + "\n"
                if data_dict:
                    for sname in sorted(data_dict.keys()):
                        min_t, max_t, wind, weather_icon = data_dict[sname]
                        wind_str = "--" if wind == 0.0 else f"{wind:.1f}m/s"
                        try:
                            avg_temp = (float(min_t) + float(max_t)) / 2
                            wd_data = {'temp': avg_temp, 'wind_speed': wind * 3.6}
                            _, rating, _ = WeatherAnalyzer.calculate_suitability(wd_data)
                            suit_emoji = WeatherAnalyzer.get_rating_emoji(rating)
                        except Exception:
                            suit_emoji = "❓"
                        temp_str = f"{min_t}~{max_t}°C"
                        sec += ljust_dw(sname, COL_NAME) + ljust_dw(temp_str, COL_TEMP) + ljust_dw(wind_str, COL_WIND) + weather_icon + suit_emoji + "\n"
                else:
                    sec += "데이터 없음 (예보 범위 초과)\n"
                sec += "```\n"
                # 풍속이 전부 0이면 중기예보 데이터 → 안내 추가
                if data_dict and all(v[2] == 0.0 for v in data_dict.values()):
                    sec += "_풍속은 5일 이내 예보에서만 제공됩니다_\n"
                sec += "\n"
                return sec

            # 이번 주 토/일 (데이터가 없는 섹션은 생략)
            if saturday_data:
                message += format_weekend_section(saturday_date, "토", saturday_data)
            if sunday_data:
                message += format_weekend_section(sunday_date, "일", sunday_data)

            # 다음 주 토/일 (오늘이 주말인 경우)
            if has_next_weekend:
                today = datetime.now(seoul_tz).date()
                next_sat_date = None
                next_sun_date = None
                for i in range(5, 14):
                    check_date = today + timedelta(days=i)
                    if check_date.weekday() == 5 and next_sat_date is None:
                        next_sat_date = check_date
                    elif check_date.weekday() == 6 and next_sun_date is None:
                        next_sun_date = check_date

                message += "*[ 다음 주 주말 ]*\n"
                message += format_weekend_section(next_sat_date, "토", next_saturday_data)
                message += format_weekend_section(next_sun_date, "일", next_sunday_data)

            return message.rstrip()
        except Exception as e:
            logger.error(f"[주말 포맷] 통합 포맷팅 오류: {e}", exc_info=True)
            return None
    
    async def send_morning_report(self) -> None:
        """매일 아침 자동 리포트 발송"""
        logger.info("아침 날씨 리포트 발송 중...")

        chat_ids = [cid.strip() for cid in Config.TELEGRAM_CHAT_ID.split(',') if cid.strip()]
        if not chat_ids:
            logger.warning("TELEGRAM_CHAT_ID가 설정되지 않아 아침 리포트를 발송하지 않습니다.")
            return

        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def fetch(site_name, site):
                return site_name, get_weekend_forecast(
                    site['latitude'],
                    site['longitude'],
                    Config.OPENWEATHER_API_KEY,
                    Config.KMA_API_KEY,
                    site.get('region')
                )

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                tasks = [
                    loop.run_in_executor(executor, fetch, name, site)
                    for name, site in self.sites.items()
                ]
                results = await asyncio.gather(*tasks)

            all_forecasts = {name: forecast for name, forecast in results}
            message = self._format_all_weekend_forecasts(all_forecasts)

            if not message:
                logger.warning("아침 리포트: 메시지 생성 실패")
                return

            for chat_id in chat_ids:
                try:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    logger.info(f"아침 리포트 발송 완료: {chat_id}")
                except Exception as e:
                    logger.error(f"아침 리포트 발송 실패 ({chat_id}): {e}")
        except Exception as e:
            logger.error(f"아침 리포트 발송 오류: {e}")
    
    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """구독 해제 명령어"""
        user = update.effective_user
        chat_id = update.effective_chat.id

        admin_ids = [cid.strip() for cid in Config.TELEGRAM_CHAT_ID.split(',') if cid.strip()]
        is_subscribed = str(chat_id) in admin_ids

        if not is_subscribed:
            await update.message.reply_text(
                "현재 자동 예보 알림이 설정되어 있지 않습니다."
            )
            return

        await update.message.reply_text(
            "알림 해제 요청이 관리자에게 전달되었습니다.\n"
            "관리자가 확인 후 알림을 해제해 드릴 예정입니다."
        )

        if admin_ids:
            admin_id = admin_ids[0]
            if str(chat_id) != admin_id:
                try:
                    username_str = f"@{user.username}" if user.username else "(없음)"
                    name_str = user.full_name or user.first_name or "?"
                    notify_msg = (
                        f"🔕 *알림 해제 요청*\n\n"
                        f"이름: {name_str}\n"
                        f"유저명: {username_str}\n"
                        f"Chat ID: `{chat_id}`\n\n"
                        f"TELEGRAM\\_CHAT\\_ID에서 이 Chat ID를 제거해 주세요."
                    )
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=notify_msg,
                        parse_mode='Markdown'
                    )
                    logger.info(f"구독 해제 요청 알림 전송: {chat_id} → 관리자({admin_id})")
                except Exception as e:
                    logger.error(f"구독 해제 알림 전송 실패: {e}")

    def create_application(self, post_init=None) -> Application:
        """텔레그램 봇 애플리케이션 생성"""
        builder = Application.builder().token(self.token)
        if post_init:
            builder = builder.post_init(post_init)
        self.application = builder.build()

        # 핸들러 추가
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("weather", self.weather_command))
        self.application.add_handler(CommandHandler("weekend", self.weekend_command))
        self.application.add_handler(CommandHandler("sites", self.sites_command))
        self.application.add_handler(CommandHandler("unsubscribe", self.unsubscribe_command))
        
        # 메시지 핸들러 (텍스트 메시지 처리)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler)
        )
        
        return self.application
    
    async def run(self) -> None:
        """봇 실행"""
        app = self.create_application()
        logger.info("텔레그램 봇 시작...")
        await app.run_polling()


if __name__ == '__main__':
    import asyncio
    
    bot = ClimbingWeatherBot(Config.TELEGRAM_BOT_TOKEN)
    # asyncio.run(bot.run())
