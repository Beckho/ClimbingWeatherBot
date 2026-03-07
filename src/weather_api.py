"""
기상 API 통합 모듈
OpenWeather API와 한국 기상청 API를 통합하여 날씨 데이터 수집
"""
import requests
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import pytz

logger = logging.getLogger(__name__)


class WeatherAPI:
    """기상 데이터 수집 클래스"""
    
    def __init__(self, openweather_key: str, kma_key: str = None):
        self.openweather_key = openweather_key
        self.kma_key = kma_key
        self.openweather_base_url = "https://api.openweathermap.org/data/2.5"
        self.kma_base_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
    
    def get_openweather(self, lat: float, lon: float) -> Optional[Dict]:
        """OpenWeather API에서 날씨 데이터 조회"""
        try:
            # 현재 날씨
            current_url = f"{self.openweather_base_url}/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.openweather_key,
                'units': 'metric',
                'lang': 'ko'
            }
            
            response = requests.get(current_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 5일 예보
            forecast_url = f"{self.openweather_base_url}/forecast"
            forecast_response = requests.get(forecast_url, params=params, timeout=10)
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
            
            # UTC 시간을 한국 시간대로 변환
            seoul_tz = pytz.timezone('Asia/Seoul')
            utc_time = datetime.fromtimestamp(data.get('dt'), tz=timezone.utc)
            kst_time = utc_time.astimezone(seoul_tz)
            
            return {
                'source': 'OpenWeather',
                'current': {
                    'temp': data.get('main', {}).get('temp'),
                    'feels_like': data.get('main', {}).get('feels_like'),
                    'humidity': data.get('main', {}).get('humidity'),
                    'pressure': data.get('main', {}).get('pressure'),
                    'wind_speed': data.get('wind', {}).get('speed'),
                    'wind_deg': data.get('wind', {}).get('deg'),
                    'clouds': data.get('clouds', {}).get('all'),
                    'rain_1h': data.get('rain', {}).get('1h', 0),
                    'description': data.get('weather', [{}])[0].get('description'),
                    'timestamp': kst_time.isoformat()
                },
                'forecast': self._parse_openweather_forecast(forecast_data)
            }
        except Exception as e:
            logger.error(f"OpenWeather API 오류: {e}")
            return None
    
    def _parse_openweather_forecast(self, data: Dict) -> List[Dict]:
        """OpenWeather 예보 데이터 파싱"""
        forecast = []
        seoul_tz = pytz.timezone('Asia/Seoul')
        
        for item in data.get('list', [])[:40]:  # 5일 데이터
            # UTC 시간을 한국 시간대로 변환
            utc_time = datetime.fromtimestamp(item.get('dt'), tz=timezone.utc)
            kst_time = utc_time.astimezone(seoul_tz)
            
            forecast.append({
                'timestamp': kst_time.isoformat(),
                'temp': item.get('main', {}).get('temp'),
                'temp_min': item.get('main', {}).get('temp_min'),
                'temp_max': item.get('main', {}).get('temp_max'),
                'humidity': item.get('main', {}).get('humidity'),
                'wind_speed': item.get('wind', {}).get('speed'),
                'rain_prob': item.get('pop', 0) * 100,
                'rain': item.get('rain', {}).get('3h', 0),
                'description': item.get('weather', [{}])[0].get('description')
            })
        return forecast
    
    def get_kma_forecast(self, lat: float, lon: float) -> Optional[Dict]:
        """한국 기상청 API에서 날씨 데이터 조회"""
        if not self.kma_key:
            logger.warning("KMA API 키가 없습니다")
            return None
        
        try:
            # 1. 위도/경도를 격자 좌표로 변환
            grid = self._convert_to_grid(lat, lon)
            if not grid:
                logger.error("좌표 변환 실패")
                return None
            
            nx, ny = grid['nx'], grid['ny']
            logger.info(f"[KMA] 좌표 변환: ({lat}, {lon}) -> 격자({nx}, {ny})")
            
            # 2. 초단기예보 조회 (실시간 데이터부터 과거로 역순 시도)
            # 기상청은 발표 후 일정 시간 지난 데이터만 제공 (보통 2-3시간)
            seoul_tz = pytz.timezone('Asia/Seoul')
            now = datetime.now(seoul_tz)
            
            short_forecast_url = f"{self.kma_base_url}/getVilageFcst"
            
            # 현재부터 과거 6시간까지 시도 (3시간 단위)
            max_attempts = 6
            for hours_back in range(max_attempts):
                attempt_dt = now - timedelta(hours=hours_back)
                fcst_date = attempt_dt.strftime('%Y%m%d')
                fcst_time = attempt_dt.strftime('%H00')
                
                short_params = {
                    'serviceKey': self.kma_key,
                    'pageNo': '1',
                    'numOfRows': '100',
                    'dataType': 'JSON',
                    'base_date': fcst_date,
                    'base_time': fcst_time,
                    'nx': str(nx),
                    'ny': str(ny)
                }
                
                try:
                    short_response = requests.get(short_forecast_url, params=short_params, timeout=10)
                    
                    if short_response.status_code != 200:
                        logger.debug(f"[KMA] 시도 {hours_back}: HTTP {short_response.status_code}")
                        continue
                    
                    short_data = short_response.json()
                    result_code = short_data.get('response', {}).get('header', {}).get('resultCode')
                    result_msg = short_data.get('response', {}).get('header', {}).get('resultMsg')
                    
                    if result_code == '00':
                        logger.info(f"[KMA] 초단기예보 조회 성공: {fcst_date} {fcst_time} ({hours_back}시간 전)")
                        
                        return {
                            'source': 'KMA',
                            'current': self._parse_kma_current(short_data),
                            'forecast': self._parse_kma_forecast(short_data)
                        }
                    else:
                        logger.debug(f"[KMA] 시도 {hours_back}: {result_msg}")
                        
                except requests.exceptions.RequestException as e:
                    logger.debug(f"[KMA] 시도 {hours_back}: 요청 오류 {e}")
                    continue
            
            logger.warning(f"[KMA] 모든 시도 실패 (최대 6시간 확인)")
            return None
            
        except Exception as e:
            logger.error(f"KMA API 오류: {e}")
            return None
    
    def _convert_to_grid(self, lat: float, lon: float) -> Optional[Dict]:
        """위도/경도를 기상청 격자 좌표로 변환"""
        try:
            import math
            
            # 기상청 공식 LCC 투영 변환
            RE = 6371.00877  # 지구 반지름(km)
            GRID = 5.0  # 격자 간격(km)
            SLAT1 = 30.0  # 표준평행선 1
            SLAT2 = 60.0  # 표준평행선 2
            OLON = 126.0  # 기준점 경도
            OLAT = 37.0  # 기준점 위도
            XO = 43  # 기준점 X
            YO = 136  # 기준점 Y
            
            DEGRAD = math.pi / 180.0
            
            slat1 = SLAT1 * DEGRAD
            slat2 = SLAT2 * DEGRAD
            olon = OLON * DEGRAD
            olat = OLAT * DEGRAD
            
            # sn: 표준평행선 비율
            sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
                math.tan(math.pi / 4.0 + slat2 / 2.0) / math.tan(math.pi / 4.0 + slat1 / 2.0)
            )
            
            # sf: 배율인자
            sf = math.tan(math.pi / 4.0 + slat1 / 2.0)
            sf = math.pow(sf, sn) * math.cos(slat1) / sn
            
            # ro: 기준점에서의 거리
            ro = math.tan(math.pi / 4.0 + olat / 2.0)
            ro = RE * sf / math.pow(ro, sn)
            
            # 대상점의 거리
            ra = math.tan(math.pi / 4.0 + lat * DEGRAD / 2.0)
            ra = RE * sf / math.pow(ra, sn)
            
            # 경도 차이 (라디안)
            theta = lon * DEGRAD - olon
            # theta 범위 정규화
            if theta > math.pi:
                theta -= 2.0 * math.pi
            if theta < -math.pi:
                theta += 2.0 * math.pi
            
            theta *= sn
            
            # 격자 좌표 계산
            x = ra * math.sin(theta) + XO * GRID
            y = ro - ra * math.cos(theta) + YO * GRID
            
            nx = int(math.floor(x / GRID + 0.5))
            ny = int(math.floor(y / GRID + 0.5))
            
            logger.debug(f"[좌표변환] ({lat:.4f}, {lon:.4f}) -> ({nx}, {ny})")
            
            return {'nx': nx, 'ny': ny}
        except Exception as e:
            logger.error(f"격자 변환 오류: {e}")
            return None
    
    def _parse_kma_current(self, data: Dict) -> Dict:
        """기상청 현재 데이터 파싱 (category별 아이템 형식)"""
        try:
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if not items:
                return {}
            
            items = items if isinstance(items, list) else [items]
            
            # 가장 빠른 예보 시간의 데이터를 수집
            earliest_categories = {}
            earliest_time = None
            
            for item in items:
                fcst_date = item.get('fcstDate', '')
                fcst_time = item.get('fcstTime', '')
                category = item.get('category', '')
                fcst_value = item.get('fcstValue', '')
                
                if not fcst_date or not fcst_time or not category:
                    continue
                
                time_key = f"{fcst_date}{fcst_time}"
                
                # 첫 번째 예보 시간만 사용 (이미 정렬되어 있음)
                if earliest_time is None:
                    earliest_time = time_key
                
                if time_key == earliest_time:
                    try:
                        value = float(fcst_value) if fcst_value else 0
                    except:
                        value = 0
                    earliest_categories[category] = value
            
            seoul_tz = pytz.timezone('Asia/Seoul')
            now = datetime.now(seoul_tz)
            
            return {
                'temp': earliest_categories.get('TMP', 0),
                'humidity': earliest_categories.get('REH', 0),
                'wind_speed': earliest_categories.get('WSD', 0),  # 이미 m/s
                'rain_1h': earliest_categories.get('RN1', 0),
                'description': self._get_kma_weather_description(earliest_categories),
                'timestamp': now.isoformat()
            }
        except Exception as e:
            logger.error(f"KMA 현재 데이터 파싱 오류: {e}")
            return {}
    
    def _parse_kma_forecast(self, data: Dict) -> List[Dict]:
        """기상청 예보 데이터 파싱 (category별 아이템 형식)"""
        forecast = []
        try:
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if not items:
                return forecast
            
            items = items if isinstance(items, list) else [items]
            seoul_tz = pytz.timezone('Asia/Seoul')
            
            # 시간별로 데이터를 모으기 (fcstDate + fcstTime을 키로)
            time_data = {}
            
            for item in items:
                fcst_date = item.get('fcstDate', '')
                fcst_time = item.get('fcstTime', '')
                category = item.get('category', '')
                fcst_value = item.get('fcstValue', '')
                
                if not fcst_date or not fcst_time or not category:
                    continue
                
                time_key = f"{fcst_date}{fcst_time}"
                
                if time_key not in time_data:
                    time_data[time_key] = {
                        'fcst_date': fcst_date,
                        'fcst_time': fcst_time,
                        'categories': {}
                    }
                
                # fcstValue를 적절한 타입으로 변환
                try:
                    value = float(fcst_value) if fcst_value else 0
                except:
                    value = 0
                
                time_data[time_key]['categories'][category] = value
            
            # 시간별 데이터를 forecast 리스트로 변환
            for time_key in sorted(time_data.keys()):
                time_info = time_data[time_key]
                categories = time_info['categories']
                
                try:
                    # 시간 정보 파싱
                    fcst_date = time_info['fcst_date']
                    fcst_time = time_info['fcst_time']
                    
                    dt_str = f"{fcst_date}{fcst_time}"
                    dt_utc = datetime.strptime(dt_str, '%Y%m%d%H%M')
                    dt_kst = dt_utc.replace(tzinfo=timezone.utc).astimezone(seoul_tz)
                    
                    # 카테고리에서 필요한 값 추출
                    forecast.append({
                        'timestamp': dt_kst.isoformat(),
                        'temp': categories.get('TMP', 0),  # 기온
                        'temp_min': categories.get('TMP', 0),
                        'temp_max': categories.get('TMP', 0),
                        'humidity': categories.get('REH', 0),  # 습도
                        'wind_speed': categories.get('WSD', 0),  # 풍속 (이미 m/s)
                        'rain_prob': categories.get('POP', 0),  # 강수확률
                        'rain': categories.get('RN1', 0),  # 1시간 강수량
                        'description': self._get_kma_weather_description(categories)
                    })
                except Exception as e:
                    logger.warning(f"KMA 시간 파싱 오류: {time_key} - {e}")
                    continue
            
            logger.info(f"[KMA] {len(forecast)}개 예보 데이터 파싱 완료 (범위: {sorted(time_data.keys())[0]}-{sorted(time_data.keys())[-1]})")
            return forecast
        except Exception as e:
            logger.error(f"KMA 예보 파싱 오류: {e}")
            return forecast
    
    def _get_kma_weather_description(self, categories: Dict) -> str:
        """기상청 데이터에서 날씨 설명 생성 (category 형식)"""
        try:
            # 기상청 코드 매핑
            sky = int(categories.get('SKY', 0))
            pty = int(categories.get('PTY', 0))
            
            # PTY (강수 형태): 0=없음, 1=비, 2=진눈깨비, 3=눈, 4=빗눈
            precipitations = {
                0: '맑음',
                1: '비',
                2: '진눈깨비',
                3: '눈',
                4: '빗눈'
            }
            
            # SKY (하늘 상태): 1=맑음, 3=흐림, 4=아주흐림
            sky_desc = {
                1: '맑음',
                3: '흐림',
                4: '아주흐림'
            }
            
            if pty != 0:
                return precipitations.get(pty, '날씨 불명')
            else:
                return sky_desc.get(sky, '날씨 불명')
        except:
            return '날씨 조회 불가'
    
    def get_multiple_forecasts(self, lat: float, lon: float) -> Dict:
        """여러 기상 API에서 데이터 수집"""
        forecasts = {}
        
        # OpenWeather
        ow_data = self.get_openweather(lat, lon)
        if ow_data:
            forecasts['openweather'] = ow_data
        
        # KMA (기상청)
        kma_data = self.get_kma_forecast(lat, lon)
        if kma_data:
            forecasts['kma'] = kma_data
        
        return forecasts


def get_weekend_forecast(lat: float, lon: float, openweather_key: str, kma_key: str = None) -> Dict:
    """주말 예보 조회 (KMA 우선, 없으면 OpenWeather)"""
    weather_api = WeatherAPI(openweather_key, kma_key)
    
    # KMA 우선으로 시도
    kma_data = weather_api.get_kma_forecast(lat, lon)
    if kma_data and kma_data.get('forecast'):
        data_source = 'kma'
        forecast_data = kma_data
        logger.info("[주말 예보] 🔵 기상청(KMA) API 사용")
    else:
        # KMA 실패하면 OpenWeather 사용
        ow_data = weather_api.get_openweather(lat, lon)
        if ow_data:
            data_source = 'openweather'
            forecast_data = ow_data
            logger.info("[주말 예보] 🟢 OpenWeather API 사용 (기상청 미응답)")
        else:
            logger.error("[주말 예보] 모든 API 호출 실패")
            return {}
    
    # 한국 시간대 기준으로 토요일과 일요일의 예보만 필터링
    seoul_tz = pytz.timezone('Asia/Seoul')
    today = datetime.now(seoul_tz).date()
    
    # 5일 예보 범위: 오늘 ~ 오늘 + 4일
    forecast_end_date = today + timedelta(days=4)
    
    # 오늘부터 다음 4일 사이에 토요일/일요일이 있는지 찾기
    saturday = None
    sunday = None
    
    for i in range(5):
        check_date = today + timedelta(days=i)
        if check_date.weekday() == 5:  # 토요일
            saturday = check_date
        elif check_date.weekday() == 6:  # 일요일
            sunday = check_date
    
    logger.info(f"[주말 예보] 오늘: {today} ({['월', '화', '수', '목', '금', '토', '일'][today.weekday()]})")
    logger.info(f"[주말 예보] 예보 범위: {today} ~ {forecast_end_date}")
    
    if saturday:
        logger.info(f"[주말 예보] 토요일: {saturday}")
    else:
        logger.info("[주말 예보] 5일 범위 내 토요일 없음")
    
    if sunday:
        logger.info(f"[주말 예보] 일요일: {sunday}")
    else:
        logger.info("[주말 예보] 5일 범위 내 일요일 없음")
    
    # 선택된 데이터 소스에서 주말 데이터 필터링
    weekend_forecast = {
        'source': data_source,
        'saturday': [],
        'sunday': [],
        'current': forecast_data.get('current')
    }
    
    forecast_list = forecast_data.get('forecast', [])
    logger.info(f"[주말 예보] {data_source}에서 {len(forecast_list)}개의 예보 데이터 수신")
    
    for forecast in forecast_list:
        try:
            forecast_timestamp = forecast.get('timestamp', '')
            forecast_date = datetime.fromisoformat(forecast_timestamp).astimezone(seoul_tz).date()
            
            if saturday and forecast_date == saturday:
                weekend_forecast['saturday'].append(forecast)
                logger.debug(f"[주말 예보] 토요일 데이터: {forecast_timestamp}")
            elif sunday and forecast_date == sunday:
                weekend_forecast['sunday'].append(forecast)
                logger.debug(f"[주말 예보] 일요일 데이터: {forecast_timestamp}")
        except Exception as e:
            logger.warning(f"[주말 예보] 타임스탬프 파싱 오류: {e}, {forecast}")
    
    sat_count = len(weekend_forecast['saturday'])
    sun_count = len(weekend_forecast['sunday'])
    logger.info(f"[주말 예보] {data_source}: 토요일 {sat_count}개, 일요일 {sun_count}개 데이터 필터링됨")
    
    return weekend_forecast


if __name__ == '__main__':
    # 테스트용 코드
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('OPENWEATHER_API_KEY')
    
    if api_key:
        # 지리산 좌표
        forecast = get_weekend_forecast(35.3167, 127.7333, api_key)
        print("주말 예보:")
        print(forecast)
