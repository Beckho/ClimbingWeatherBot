# 🏔️ 클라이밍 날씨 TGTWTG 봇

여러 기상 API를 통합하여 주말 야외 클라이밍 적합도를 분석하고, 텔레그램으로 자동 알림을 전송하는 Python 기반 봇입니다.

## 주요 기능

✅ **정확한 기상 API 통합**
- OpenWeather API를 통한 5일 예보 데이터
- 한국 시간대 기반 정시 데이터 변환
- 향후 한국 기상청 API 추가 예정

✅ **실시간 주말 날씨 분석**
- 최저/최고 온도 표시
- 날씨 상태 아이콘 (☀️맑음, ☁️흐림, 🌧️비, 등)
- 5일 범위 내 주말 예보 (오늘로부터 5일 이내 주말)
- 13개 주요 클라이밍 지역 종합 비교

✅ **텔레그램 자동 알림**
- 매일 아침 설정 시간에 자동 리포트 발송 (기본 7:00)
- 실시간 명령어를 통한 즉시 조회
- 자연스러운 텍스트 기반 명령 인식

✅ **13개 클라이밍 지역 모니터링**

**스포츠 클라이밍 (7개)**
- 간현, 조비산, 선운산, 삼성산, 삼천바위, 연경도약대, 새벽암장

**볼더링 (6개)**
- 운일암 반일암, 무등산, 북한산, 불암산, 감자바위, 을왕리

## 설치 방법

### 1. 필수 요구사항
- Python 3.9 이상
- pip 패키지 매니저

### 2. 저장소 클론 및 의존성 설치
```bash
# 저장소 클론
git clone <repository-url>
cd climbing-weather-bot

# 가상환경 생성 (권장)
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env.example` 파일을 `.env`로 복사하고 필수 정보를 입력합니다:

```bash
cp .env.example .env
```

`.env` 파일에 입력할 필수 정보:
```
# Telegram Bot Token (필수)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# OpenWeather API Key (필수)
OPENWEATHER_API_KEY=your_openweather_api_key

# 아침 자동 리포트 시간 (선택)
SCHEDULE_HOUR=7
SCHEDULE_MINUTE=0
```

## API 키 획득 방법

### Telegram 봇 토큰 & Chat ID
1. **봇 토큰 생성**
   - [BotFather](https://t.me/botfather)와 대화
   - `/newbot` 명령으로 새 봇 생성
   - 받은 토큰을 `.env` 파일의 `TELEGRAM_BOT_TOKEN`에 입력

2. **Chat ID 확인**
   - 생성한 봇을 Telegram에서 추가
   - `/start` 명령 실행
   - 봇 로그(logs/weather_bot.log)에서 Chat ID 확인
   - 또는 [@userinfobot](https://t.me/userinfobot) 사용

### OpenWeather API 키
1. [OpenWeatherMap](https://openweathermap.org/api) 접속
2. Free 회원 가입 및 로그인
3. "API Keys" 탭에서 키 복사
4. `.env` 파일의 `OPENWEATHER_API_KEY`에 입력

## 사용 방법

### 봇 실행
```bash
python src/main.py
```

### 텔레그램 명령어
```
/start     - 봇 정보 및 초기 인사
/weather   - 모든 지역의 현재 날씨 조회
/weekend   - 이번 주말 예보 (표 형식 통합 표시)
/sites     - 등록된 13개 클라이밍 지역 목록
/help      - 상세한 도움말
```

### 자연스러운 텍스트 명령 인식
봇은 다음과 같은 텍스트도 이해합니다:

- **날씨 조회**: "날씨", "날씨 어때", "예보", "조회"
  - 예: "빰람 날씨봐", "예보 뭐야"
  
- **주말 예보**: "주말", "주말날씨", "토요일", "일요일"
  - 예: "주말 어때요?", "일요일 날씨 알려줘"
  
- **지역 정보**: "지역", "목록", "어디", "있는"
  - 예: "어떤 지역 있어?", "목록 보여줘"

## 주말 예보 예시

`/weekend` 명령을 실행하면 다음과 같은 표 형식으로 받습니다:

```
🗓️ [ 주말 날씨 예보 ]
최저/최고 온도 (5일 이내)
═══════════════════════════════════════════════

📅 토요일 - 03-08 (토)
지역           온도        
────────────────────────
간현           5~15°C    ☀️
조비산         6~14°C    ☁️
선운산         7~16°C    ☀️
삼성산         6~15°C    ☀️
삼천바위       8~17°C    ☁️
...

📅 일요일 - 03-09 (일)
지역           온도        
────────────────────────
간현           6~16°C    ☀️
...
```

> 📌 **주의**: 5일 예보는 오늘 기준으로 5일 이내 범위만 제공됩니다.
> 주말이 5일 범위를 벗어나면 가장 가까운 주말의 예보를 표시합니다.

## 날씨 아이콘 설명

| 아이콘 | 날씨 상태 |
|--------|---------|
| ☀️ | 맑음 |
| ☁️ | 흐림 / 구름 |
| 🌧️ | 비 |
| ❄️ | 눈 |
| ⛈️ | 뇌우 |
| 🌫️ | 안개 |

## 프로젝트 구조

```
climbing-weather-bot/
├── src/
│   ├── main.py              # 메인 진입점 & 봇 실행
│   ├── config.py            # 설정 & 환경변수 관리
│   ├── weather_api.py       # OpenWeather API 통합
│   ├── telegram_bot.py      # 텔레그램 봇 구현 & 명령어 핸들러
│   ├── scheduler.py         # APScheduler를 이용한 자동 스케줄링
│   └── __init__.py          # 패키지 초기화
│
├── config/
│   └── sites.json           # 13개 클라이밍 지역 설정 (좌표 포함)
│
├── logs/                    # 로그 파일 저장소
│   └── weather_bot.log      # 실행 로그 (Chat ID 확인 용도)
│
├── requirements.txt         # Python 의존성
├── .env.example            # 환경변수 템플릿
└── README.md               # 이 파일
```

## 설정 커스터마이징

### 클라이밍 지역 추가/수정
`config/sites.json` 수정 예시:

```json
{
  "sites": [
    {
      "name": "새로운 지역",
      "latitude": 37.2345,
      "longitude": 127.1234,
      "region": "경기도",
      "type": "스포츠 클라이밍"
    }
  ]
}
```

### 아침 자동 리포트 시간 변경
`.env` 파일:
```
SCHEDULE_HOUR=8      # 아침 8시
SCHEDULE_MINUTE=30   # 30분
```

## 로깅

모든 활동은 `logs/weather_bot.log` 파일에 기록됩니다.

**로그 확인 용도:**
- Chat ID 확인: 봇 실행 후 `/start` 명령 실행 → 로그의 "Chat ID" 확인
- API 오류 추적
- 자동 스케줄 실행 기록
- 명령어 실행 기록

## 문제 해결

### "모듈을 찾을 수 없습니다" 오류
```
ModuleNotFoundError: No module named 'telegram'
```
→ `pip install -r requirements.txt`로 의존성을 재설치하세요.

### "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다"
→ `.env` 파일이 `src/` 폴더와 같은 레벨(루트)에 있는지 확인
→ `.env` 파일에 토큰이 올바르게 입력되었는지 확인

### "Chat ID가 설정되지 않았습니다"
→ 봇에 `/start` 명령 실행
→ `logs/weather_bot.log`에서 Chat ID 확인
→ `.env` 파일에 입력

### 봇이 메시지에 응답하지 않음
1. 봇 토큰과 Chat ID가 올바른지 확인
2. `logs/weather_bot.log` 파일 확인
3. 텔레그램 봇이 활성화되어 있는지 확인 (@BotFather에서 확인)

### "API 키가 설정되지 않았습니다" 또는 날씨 데이터 없음
1. OpenWeather API 키가 `.env`에 입력되었는지 확인
2. API 할당량 초과 확인 (Free: 1,000/일 제한)
3. `logs/weather_bot.log`에서 API 오류 메시지 확인

### 주말 예보가 나오지 않음
→ 5일 범위 내에 주말이 없을 수 있습니다.
→ 각 요일별로 확인: 월(0), 화(1), 수(2), 목(3), 금(4), 토(5), 일(6)

## 의존성

- **python-telegram-bot** (20.3): 텔레그램 봇 라이브러리
- **requests** (2.31.0): HTTP 요청
- **python-dotenv** (1.0.0): 환경변수 관리
- **APScheduler** (3.10.4): 자동 스케줄링
- **pytz** (2024.1): 시간대 변환

## 향후 개선 사항

- [ ] 한국 기상청 API 통합
- [ ] 클라이밍 적합도 점수 시스템 구현
- [ ] 웹 대시보드 추가
- [ ] 시간대별 상세 예보 (3시간 단위)
- [ ] 사용자 맞춤 지역 설정
- [ ] 이상 기후 알림 기능
- [ ] 더 많은 클라이밍 지역 추가
- [ ] 카카오톡 봇 지원 (정책 허용 시)

## 라이센스

MIT License

## 기여

버그 리포트 및 기능 제안은 이슈로 등록해주세요.

## 문의

문제가 있으시면 이슈를 생성해주세요.

---

**마지막 업데이트**: 2026년 3월 7일
**프로젝트 상태**: 주말 예보 기능 완성, 정상 운영 중
**개발**: Climbing Weather Bot Development Team

