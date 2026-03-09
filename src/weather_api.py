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

# 인메모리 캐시
_forecast_cache: dict = {}          # {lat,lon: (ts, data)} - 단기예보
_midterm_cache: dict = {}           # {region: (ts, data)} - 중기예보
_CACHE_TTL_SECONDS = 3 * 60 * 60   # 3시간 (단기)
_MIDTERM_TTL_SECONDS = 6 * 60 * 60 # 6시간 (중기, 하루 2회 발표)


class WeatherAPI:
    """기상 데이터 수집 클래스"""
    
    def __init__(self, openweather_key: str, kma_key: str = None):
        self.openweather_key = openweather_key
        self.kma_key = kma_key
        self.openweather_base_url = "https://api.openweathermap.org/data/2.5"
        self.kma_base_url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
        self.kma_mid_base_url = "https://apis.data.go.kr/1360000/MidFcstInfoService"
    
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

            # 기상청 유효 발표 시각 (getVilageFcst는 이 시각에만 데이터 제공)
            valid_base_times = ['2300', '2000', '1700', '1400', '1100', '0800', '0500', '0200']

            # 현재 시각 기준으로 가장 최근 유효 발표 시각 목록 생성 (최대 2일치 시도)
            candidates = []
            for days_back in range(2):
                check_dt = now - timedelta(days=days_back)
                for bt in valid_base_times:
                    candidates.append((check_dt.strftime('%Y%m%d'), bt))

            for fcst_date, fcst_time in candidates:
                
                short_params = {
                    'serviceKey': self.kma_key,
                    'pageNo': '1',
                    'numOfRows': '1000',
                    'dataType': 'JSON',
                    'base_date': fcst_date,
                    'base_time': fcst_time,
                    'nx': str(nx),
                    'ny': str(ny)
                }
                
                try:
                    short_response = requests.get(short_forecast_url, params=short_params, timeout=5)
                    
                    if short_response.status_code != 200:
                        logger.debug(f"[KMA] 시도 {fcst_date} {fcst_time}: HTTP {short_response.status_code}")
                        continue

                    short_data = short_response.json()
                    result_code = short_data.get('response', {}).get('header', {}).get('resultCode')
                    result_msg = short_data.get('response', {}).get('header', {}).get('resultMsg')

                    if result_code == '00':
                        logger.info(f"[KMA] 초단기예보 조회 성공: {fcst_date} {fcst_time}")
                        announced_at = f"{fcst_date[:4]}-{fcst_date[4:6]}-{fcst_date[6:8]} {fcst_time[:2]}:{fcst_time[2:]}"

                        return {
                            'source': 'KMA',
                            'current': self._parse_kma_current(short_data),
                            'forecast': self._parse_kma_forecast(short_data),
                            'announced_at': announced_at
                        }
                    else:
                        logger.warning(f"[KMA] 시도 {fcst_date} {fcst_time}: code={result_code} msg={result_msg}")
                        # 인증 오류(20)나 서비스 키 오류면 더 시도해도 의미 없음
                        if result_code in ('20', '22', '10', '12'):
                            break

                except requests.exceptions.RequestException as e:
                    logger.warning(f"[KMA] 시도 {fcst_date} {fcst_time}: 요청 오류 {e}")
                    continue

            logger.warning(f"[KMA] 모든 시도 실패")
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
                    # KMA fcstDate/fcstTime은 KST이므로 바로 localize
                    dt_kst = seoul_tz.localize(datetime.strptime(dt_str, '%Y%m%d%H%M'))
                    
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
    
    def get_kma_midterm_forecast(self, region: str) -> Optional[Dict]:
        """KMA 중기예보 조회 (D+3~D+10) - 지역명 기반"""
        if not self.kma_key:
            return None

        # 중기육상예보 지역 코드 (getMidLandFcst)
        land_reg_map = {
            '서울':     '11B00000',
            '경기도':   '11B00000',
            '인천':     '11B00000',
            '강원도':   '11D10000',
            '전라북도': '11F10000',
            '전라남도': '11F20000',
            '광주':     '11F20000',
            '경상북도': '11H10000',
            '대구':     '11H10000',
            '경상남도': '11H20000',
            '부산':     '11H20000',
            '울산':     '11H20000',
        }
        # 중기기온조회 지역 코드 (getMidTa)
        ta_reg_map = {
            '서울':     '11B10101',
            '경기도':   '11B20601',  # 수원
            '인천':     '11B20201',
            '강원도':   '11D10401',  # 원주 (영서)
            '전라북도': '11F10201',  # 전주
            '전라남도': '11F20401',  # 순천
            '광주':     '11F20501',
            '경상북도': '11H10201',  # 안동
            '대구':     '11H10701',
            '경상남도': '11H20101',  # 창원
            '부산':     '11H20201',
            '울산':     '11H20301',
        }

        land_reg_id = land_reg_map.get(region)
        ta_reg_id = ta_reg_map.get(region)
        if not land_reg_id or not ta_reg_id:
            logger.warning(f"[KMA 중기] 알 수 없는 지역: {region}")
            return None

        seoul_tz = pytz.timezone('Asia/Seoul')
        now = datetime.now(seoul_tz)

        # tmFc: 0600 또는 1800 KST (발표 기준시각)
        if now.hour >= 18:
            tmFc = now.strftime('%Y%m%d') + '1800'
        elif now.hour >= 6:
            tmFc = now.strftime('%Y%m%d') + '0600'
        else:
            tmFc = (now - timedelta(days=1)).strftime('%Y%m%d') + '1800'

        common_params = {
            'serviceKey': self.kma_key,
            'pageNo': '1',
            'numOfRows': '10',
            'dataType': 'JSON',
            'tmFc': tmFc,
        }

        # 캐시 확인
        import time as _time
        cached = _midterm_cache.get(region)
        if cached:
            cached_ts, cached_data = cached
            if _time.time() - cached_ts < _MIDTERM_TTL_SECONDS:
                logger.info(f"[KMA 중기] {region} 캐시 사용")
                return cached_data

        try:
            land_resp = requests.get(
                f"{self.kma_mid_base_url}/getMidLandFcst",
                params={**common_params, 'regId': land_reg_id}, timeout=5
            )
            ta_resp = requests.get(
                f"{self.kma_mid_base_url}/getMidTa",
                params={**common_params, 'regId': ta_reg_id}, timeout=5
            )

            logger.info(f"[KMA 중기] getMidLandFcst HTTP {land_resp.status_code}, getMidTa HTTP {ta_resp.status_code}")

            if land_resp.status_code != 200:
                logger.warning(f"[KMA 중기] getMidLandFcst 오류 응답: {land_resp.text[:200]}")
                return None
            if ta_resp.status_code != 200:
                logger.warning(f"[KMA 중기] getMidTa 오류 응답: {ta_resp.text[:200]}")
                return None

            land_json = land_resp.json()
            ta_json = ta_resp.json()

            land_code = land_json.get('response', {}).get('header', {}).get('resultCode')
            ta_code = ta_json.get('response', {}).get('header', {}).get('resultCode')
            if land_code != '00':
                logger.warning(f"[KMA 중기] getMidLandFcst resultCode={land_code} msg={land_json.get('response',{}).get('header',{}).get('resultMsg')}")
                return None
            if ta_code != '00':
                logger.warning(f"[KMA 중기] getMidTa resultCode={ta_code} msg={ta_json.get('response',{}).get('header',{}).get('resultMsg')}")
                return None

            land_items = land_json.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            ta_items = ta_json.get('response', {}).get('body', {}).get('items', {}).get('item', [])

            land_item = land_items[0] if isinstance(land_items, list) and land_items else land_items if isinstance(land_items, dict) else {}
            ta_item = ta_items[0] if isinstance(ta_items, list) and ta_items else ta_items if isinstance(ta_items, dict) else {}

            if not land_item or not ta_item:
                logger.warning(f"[KMA 중기] {region} 응답 데이터 없음 (tmFc={tmFc})")
                return None

            # D+3~D+10 날짜별 forecast 생성
            today = now.date()
            forecast = []
            for d in range(3, 11):
                fcst_date = today + timedelta(days=d)
                # 3~7일은 오전/오후 구분, 8~10일은 통합
                if d <= 7:
                    rain_prob = (land_item.get(f'rnSt{d}Am', 0) + land_item.get(f'rnSt{d}Pm', 0)) / 2
                    weather = land_item.get(f'wf{d}Pm') or land_item.get(f'wf{d}Am') or ''
                else:
                    rain_prob = land_item.get(f'rnSt{d}', 0)
                    weather = land_item.get(f'wf{d}', '')

                temp_min = ta_item.get(f'taMin{d}', 0)
                temp_max = ta_item.get(f'taMax{d}', 0)

                forecast.append({
                    'timestamp': datetime.combine(fcst_date, datetime.min.time()).replace(tzinfo=seoul_tz).isoformat(),
                    'temp': (temp_min + temp_max) / 2,
                    'temp_min': temp_min,
                    'temp_max': temp_max,
                    'humidity': 0,
                    'wind_speed': 0,
                    'rain_prob': rain_prob,
                    'rain': 0,
                    'description': weather
                })

            result = {
                'source': 'KMA_mid',
                'forecast': forecast,
                'announced_at': f"{tmFc[:4]}-{tmFc[4:6]}-{tmFc[6:8]} {tmFc[8:10]}:00"
            }
            logger.info(f"[KMA 중기] {region}: {len(forecast)}일치 예보 완료 (tmFc={tmFc})")
            _midterm_cache[region] = (_time.time(), result)
            return result

        except Exception as e:
            logger.error(f"[KMA 중기] {region} 오류: {e}")
            return None

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


def get_weekend_forecast(lat: float, lon: float, openweather_key: str, kma_key: str = None, region: str = None) -> Dict:
    """주말 예보 조회 (KMA 우선, 없으면 OpenWeather) - 3시간 캐시 적용"""
    import time
    cache_key = f"{lat:.4f},{lon:.4f}"
    now_ts = time.time()

    # 캐시 히트
    if cache_key in _forecast_cache:
        cached_ts, cached_data = _forecast_cache[cache_key]
        if now_ts - cached_ts < _CACHE_TTL_SECONDS:
            logger.info(f"[캐시] {cache_key} 캐시 사용 (남은시간: {int((_CACHE_TTL_SECONDS - (now_ts - cached_ts)) / 60)}분)")
            return cached_data

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

    # 오늘이 주말(토/일)이면 다음 주 주말도 표시
    today_weekday = today.weekday()
    is_weekend_today = today_weekday in (5, 6)

    # 이번 주 주말 날짜 (ISO 주 기준: 월~일)
    # 오늘이 일요일이면 토요일은 어제(과거), 일요일은 오늘
    # 그 외에는 이번 주 혹은 다음 주 토/일 중 가장 가까운 날
    if today_weekday == 6:  # 일요일
        saturday = today - timedelta(days=1)  # 어제 (데이터 없음, 표시용)
        sunday = today
    else:
        saturday = None
        sunday = None
        for i in range(8):
            check_date = today + timedelta(days=i)
            if check_date.weekday() == 5 and saturday is None:
                saturday = check_date
            elif check_date.weekday() == 6 and sunday is None:
                sunday = check_date
            if saturday and sunday:
                break

    # 다음 주 주말 날짜 찾기 (오늘이 주말인 경우)
    next_saturday = None
    next_sunday = None
    if is_weekend_today:
        for i in range(5, 14):
            check_date = today + timedelta(days=i)
            if check_date.weekday() == 5 and next_saturday is None:
                next_saturday = check_date
            elif check_date.weekday() == 6 and next_sunday is None:
                next_sunday = check_date

    logger.info(f"[주말 예보] 오늘: {today} ({['월', '화', '수', '목', '금', '토', '일'][today.weekday()]})")
    logger.info(f"[주말 예보] 이번 주말: 토={saturday}, 일={sunday}")
    if is_weekend_today:
        logger.info(f"[주말 예보] 다음 주말: 토={next_saturday}, 일={next_sunday}")

    # 선택된 데이터 소스에서 주말 데이터 필터링
    announced_at = forecast_data.get('announced_at') if data_source == 'kma' else None

    weekend_forecast = {
        'source': data_source,
        'saturday': [],
        'sunday': [],
        'current': forecast_data.get('current'),
        'announced_at': announced_at
    }

    if is_weekend_today:
        weekend_forecast['next_saturday'] = []
        weekend_forecast['next_sunday'] = []

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
            elif is_weekend_today and next_saturday and forecast_date == next_saturday:
                weekend_forecast['next_saturday'].append(forecast)
            elif is_weekend_today and next_sunday and forecast_date == next_sunday:
                weekend_forecast['next_sunday'].append(forecast)
        except Exception as e:
            logger.warning(f"[주말 예보] 타임스탬프 파싱 오류: {e}, {forecast}")

    sat_count = len(weekend_forecast['saturday'])
    sun_count = len(weekend_forecast['sunday'])
    logger.info(f"[주말 예보] {data_source}: 토요일 {sat_count}개, 일요일 {sun_count}개 데이터 필터링됨")

    # KMA 중기예보 보완:
    # 1) 오늘이 주말 → 다음 주 토/일 채우기
    # 2) 이번 주 토/일이 단기예보 범위(3일) 초과 → 이번 주 토/일도 중기예보로 채우기
    days_to_saturday = (saturday - today).days if saturday else 0
    days_to_sunday = (sunday - today).days if sunday else 0

    need_midterm_sat = bool(saturday and days_to_saturday > 3)
    need_midterm_sun = bool(sunday and days_to_sunday > 3)
    need_midterm_this_week = need_midterm_sat or need_midterm_sun

    if region and kma_key and (is_weekend_today or need_midterm_this_week):
        midterm_data = weather_api.get_kma_midterm_forecast(region)
        if midterm_data:
            # 날짜별 중기예보 맵 생성
            midterm_by_date = {}
            for fc in midterm_data.get('forecast', []):
                try:
                    fc_date = datetime.fromisoformat(fc['timestamp']).astimezone(seoul_tz).date()
                    midterm_by_date[fc_date] = fc
                except Exception as e:
                    logger.warning(f"[KMA 중기] 타임스탬프 파싱 오류: {e}")

            def merge_with_midterm(short_items, midterm_fc):
                """단기예보(풍속/날씨) + 중기예보(최저/최고온도) 합성"""
                if short_items and midterm_fc:
                    avg_wind = sum(item.get('wind_speed', 0) for item in short_items) / len(short_items)
                    desc = short_items[0].get('description', midterm_fc.get('description', ''))
                    return [{
                        'temp_min': midterm_fc.get('temp_min', 0),
                        'temp_max': midterm_fc.get('temp_max', 0),
                        'temp': midterm_fc.get('temp', 0),
                        'wind_speed': avg_wind,
                        'rain_prob': midterm_fc.get('rain_prob', 0),
                        'description': desc,
                        'timestamp': midterm_fc.get('timestamp', ''),
                    }]
                elif midterm_fc:
                    return [midterm_fc]
                else:
                    return short_items

            if need_midterm_sat and saturday and saturday in midterm_by_date:
                weekend_forecast['saturday'] = merge_with_midterm(
                    weekend_forecast['saturday'], midterm_by_date[saturday]
                )
            if need_midterm_sun and sunday and sunday in midterm_by_date:
                weekend_forecast['sunday'] = merge_with_midterm(
                    weekend_forecast['sunday'], midterm_by_date[sunday]
                )
            if is_weekend_today:
                if next_saturday and next_saturday in midterm_by_date:
                    weekend_forecast['next_saturday'] = merge_with_midterm(
                        weekend_forecast.get('next_saturday', []), midterm_by_date[next_saturday]
                    )
                if next_sunday and next_sunday in midterm_by_date:
                    weekend_forecast['next_sunday'] = merge_with_midterm(
                        weekend_forecast.get('next_sunday', []), midterm_by_date[next_sunday]
                    )

            logger.info(f"[KMA 중기 합성] 이번주 토={len(weekend_forecast['saturday'])}개, 일={len(weekend_forecast['sunday'])}개 / 다음주 토={len(weekend_forecast.get('next_saturday',[]))}개, 일={len(weekend_forecast.get('next_sunday',[]))}개")

    # 캐시 저장
    _forecast_cache[cache_key] = (time.time(), weekend_forecast)

    return weekend_forecast


def refresh_all_sites_cache(sites: list, openweather_key: str, kma_key: str = None) -> None:
    """모든 지역 캐시 강제 갱신 (스케줄러 호출용)"""
    from concurrent.futures import ThreadPoolExecutor

    def fetch_site(site):
        cache_key = f"{site['latitude']:.4f},{site['longitude']:.4f}"
        _forecast_cache.pop(cache_key, None)  # 기존 캐시 무효화 후 새로 가져옴
        get_weekend_forecast(site['latitude'], site['longitude'], openweather_key, kma_key, site.get('region'))

    logger.info(f"[캐시 갱신] {len(sites)}개 지역 갱신 시작...")
    with ThreadPoolExecutor() as executor:
        list(executor.map(fetch_site, sites))
    logger.info("[캐시 갱신] 완료")


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
