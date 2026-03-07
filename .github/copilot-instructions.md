# 클라이밍 날씨 TGTWTG 봇 - 프로젝트 설정

## 프로젝트 개요
여러 기상 API를 통합하여 주말 야외 클라이밍 적합도를 분석하고,
텔레그램으로 자동 알림을 전송하는 Python 기반 봇 서비스.

## 주요 요구사항
- Python으로 구현
- OpenWeather API + 한국 기상청 API 통합
- 주요 클라이밍 지역별 날씨 분석
- 테스트 > 온도, 강수, 바람, 미세먼지 등
- 텔레그램 봇으로 실시간 알림
- 매일 아침 7시 자동 알림
- 사용자 요청시 즉시 조회

## 프로젝트 구조
```
climbing-weather-bot/
├── src/
│   ├── main.py           # 메인 진입점
│   ├── config.py         # 설정 관리
│   ├── weather_api.py    # 기상 API 통합
│   ├── analyzer.py       # 날씨 분석
│   ├── telegram_bot.py   # 텔레그램 봇
│   ├── scheduler.py      # 자동 스케줄링
│   └── __init__.py
├── config/
│   └── sites.json        # 클라이밍 지역 설정
├── logs/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 설정 완료 사항

### ✓ 1. 프로젝트 구조 설정
- src/ 디렉토리: Python 모듈
- config/ 디렉토리: 설정 파일
- logs/ 디렉토리: 로그 저장소

### ✓ 2. 핵심 모듈 구현
- **main.py**: 애플리케이션 진입점, 봇 실행 및 스케줄러 관리
- **config.py**: 환경변수 및 설정 로드, 유효성 검증
- **weather_api.py**: OpenWeather API 통합, 다중 예보 수집
- **analyzer.py**: 날씨 분석, 클라이밍 적합도 판정 (0-100점)
- **telegram_bot.py**: 텔레그램 봇 구현, 명령어 처리
- **scheduler.py**: APScheduler를 이용한 자동 스케줄링

### ✓ 3. 설정 파일
- **.env.example**: 환경변수 템플릿
- **config/sites.json**: 6개 주요 클라이밍 지역, 날씨 기준값

### ✓ 4. 의존성
```
python-telegram-bot==20.3
requests==2.31.0
python-dotenv==1.0.0
APScheduler==3.10.4
aiohttp==3.9.1
Pillow==10.1.0
```

## 다음 단계

### 1. 환경 변수 설정 (필수)
```bash
cp .env.example .env
# .env 파일 편집:
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_CHAT_ID  
# - OPENWEATHER_API_KEY
```

### 2. Python 환경 설정
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. 봇 실행
```bash
python src/main.py
```

### 4. 텔레그램 테스트
- 봇에 `/start` 명령 전송
- `/weather` 명령으로 현재 날씨 조회
- `/weekend` 명령으로 주말 예보 조회

## 주요 기능

### 날씨 분석 (Analyzer)
- 온도: 5-30°C 최적
- 바람: 30km/h 이하
- 습도: 80% 이하
- 강수: 3mm 이상 시 감점
- 5단계 평점: 완벽🟢, 좋음🟡, 중간🟠, 안좋음🔴, 매우안좋음⛔

### 봇 명령어
- /start - 초기 인사
- /weather - 현재 날씨 조회
- /weekend - 주말 예보
- /sites - 등록된 지역 목록
- /help - 도움말

### 자동 기능
- 매일 아침 7시 (설정 가능) 자동 리포트
- 사용자 메시지 텍스트 분석 기반 응답

## 알려진 제약사항

1. **한국 기상청 API**: 향후 추가 예정 (현재 OpenWeather만 지원)
2. **카카오톡 연동**: 카카오 정책상 어려움 (텔레그램만 지원)
3. **API 할당량**: OpenWeather Free Plan은 1일 1000건 제한

## 기술 스택

- **언어**: Python 3.9+
- **텔레그램 봇**: python-telegram-bot 20.3
- **스케줄링**: APScheduler 3.10.4
- **HTTP 클라이언트**: requests 2.31.0
- **환경 관리**: python-dotenv 1.0.0

## 개발 노트

- 모든 API 호출은 에러 핸들링 포함
- 로깅은 파일과 콘솔 모두에 기록
- 비동기 처리로 반응성 향상
- 설정은 .env 파일로 중앙화

## 참고 문서

- [OpenWeather API 문서](https://openweathermap.org/api)
- [python-telegram-bot 문서](https://python-telegram-bot.readthedocs.io/)
- [APScheduler 문서](https://apscheduler.readthedocs.io/)

---

**프로젝트 생성일**: 2026년 3월 7일  
**상태**: 설정 완료, 실행 준비 완료  
**다음 작업**: API 키 설정 후 봇 실행
