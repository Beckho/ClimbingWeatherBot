"""
날씨 분석 및 클라이밍 적합도 판단 모듈
"""
import logging
from datetime import datetime
from typing import Dict, List, Tuple
import json

logger = logging.getLogger(__name__)


class WeatherAnalyzer:
    """날씨 분석 및 평가 클래스"""
    
    # 클라이밍 적합도 기준
    CRITERIA = {
        'wind_speed_max': 30,      # km/h
        'temp_min': 5,             # °C
        'temp_max': 30,            # °C
        'rain_threshold': 3.0,     # mm
        'humidity_max': 80,        # %
        'pm25_max': 35             # μg/m³
    }
    
    RATING_SCALE = {
        'perfect': (90, 100),
        'good': (70, 89),
        'fair': (50, 69),
        'poor': (30, 49),
        'very_poor': (0, 29)
    }
    
    @staticmethod
    def calculate_suitability(weather_data: Dict, criteria: Dict = None) -> Tuple[int, str]:
        """날씨 적합도 계산 (0-100)"""
        if criteria is None:
            criteria = WeatherAnalyzer.CRITERIA
        
        score = 100
        penalties = {}
        
        # 온도 평가
        temp = weather_data.get('temp')
        if temp is not None:
            if temp < criteria['temp_min']:
                penalties['too_cold'] = (criteria['temp_min'] - temp) * 5
            elif temp > criteria['temp_max']:
                penalties['too_hot'] = (temp - criteria['temp_max']) * 3
        
        # 바람 평가
        wind = weather_data.get('wind_speed')
        if wind is not None:
            if wind > criteria['wind_speed_max']:
                penalties['too_windy'] = (wind - criteria['wind_speed_max']) * 2
        
        # 강수량 평가
        rain = weather_data.get('rain_1h', 0)
        if rain > criteria['rain_threshold']:
            penalties['rain'] = (rain - criteria['rain_threshold']) * 10
        
        # 습도 평가
        humidity = weather_data.get('humidity')
        if humidity and humidity > criteria['humidity_max']:
            penalties['humidity'] = (humidity - criteria['humidity_max']) * 0.3
        
        # 강수 확률 평가 (예보)
        rain_prob = weather_data.get('rain_prob', 0)
        if rain_prob > 50:
            penalties['rain_probability'] = (rain_prob - 50) * 0.5
        
        # 점수 계산
        for penalty in penalties.values():
            score -= penalty
        
        score = max(0, min(100, int(score)))
        
        # 평점 결정
        rating = WeatherAnalyzer._get_rating(score)
        
        return score, rating, penalties
    
    @staticmethod
    def _get_rating(score: int) -> str:
        """점수를 평점으로 변환"""
        for rating, (min_score, max_score) in WeatherAnalyzer.RATING_SCALE.items():
            if min_score <= score <= max_score:
                return rating
        return 'unknown'
    
    @staticmethod
    def get_rating_emoji(rating: str) -> str:
        """평점 이모지"""
        emojis = {
            'perfect': '🟢',
            'good': '🟡',
            'fair': '🟠',
            'poor': '🔴',
            'very_poor': '⛔'
        }
        return emojis.get(rating, '❓')
    
    @staticmethod
    def get_rating_description(rating: str) -> str:
        """평점 설명"""
        descriptions = {
            'perfect': '완벽한 조건 - 클라이밍 최적',
            'good': '좋은 조건 - 클라이밍 권장',
            'fair': '중간 조건 - 주의 필요',
            'poor': '안 좋은 조건 - 비권장',
            'very_poor': '아주 안 좋은 조건 - 위험'
        }
        return descriptions.get(rating, '알 수 없음')
    
    @staticmethod
    def analyze_site(site_name: str, site_data: Dict, weather_apis: Dict) -> Dict:
        """특정 지역의 날씨 종합 분석"""
        analysis = {
            'site': site_name,
            'timestamp': datetime.now().isoformat(),
            'sources': {},
            'summary': {}
        }
        
        # 각 API별 분석
        for source, data in weather_apis.items():
            if data and 'current' in data:
                current = data['current'].copy()
                score, rating, penalties = WeatherAnalyzer.calculate_suitability(current)
                
                analysis['sources'][source] = {
                    'weather': current,
                    'suitability': {
                        'score': score,
                        'rating': rating,
                        'emoji': WeatherAnalyzer.get_rating_emoji(rating),
                        'description': WeatherAnalyzer.get_rating_description(rating),
                        'penalties': {k: round(v, 2) for k, v in penalties.items()}
                    },
                    'recommendations': WeatherAnalyzer.get_recommendations(current)
                }
        
        # 종합 점수 계산
        if analysis['sources']:
            avg_score = sum(
                s['suitability']['score'] for s in analysis['sources'].values()
            ) / len(analysis['sources'])
            avg_rating = WeatherAnalyzer._get_rating(int(avg_score))
            
            analysis['summary'] = {
                'average_score': round(avg_score, 1),
                'rating': avg_rating,
                'emoji': WeatherAnalyzer.get_rating_emoji(avg_rating),
                'sources_count': len(analysis['sources'])
            }
        
        return analysis
    
    @staticmethod
    def get_recommendations(weather_data: Dict) -> List[str]:
        """날씨에 따른 권장사항"""
        recommendations = []
        
        temp = weather_data.get('temp')
        wind = weather_data.get('wind_speed')
        humidity = weather_data.get('humidity')
        rain = weather_data.get('rain_1h', 0)
        
        # 온도
        if temp is not None:
            if temp < 5:
                recommendations.append("기온이 매우 낮습니다. 방한용품을 충분히 준비하세요.")
            elif temp < 10:
                recommendations.append("날씨가 쌀쌀하므로 따뜻한 복장이 필요합니다.")
            elif temp > 28:
                recommendations.append("기온이 높습니다. 충분한 수분 섭취와 자외선 차단제를 준비하세요.")
        
        # 바람
        if wind and wind > 20:
            recommendations.append(f"풍속이 강합니다 ({wind:.1f}km/h). 안전에 주의하세요.")
        
        # 습도
        if humidity and humidity > 75:
            recommendations.append("습도가 높아 미끄러울 수 있습니다. 안전에 주의하세요.")
        
        # 강수
        if rain > 0:
            recommendations.append(f"강수가 예상됩니다 ({rain:.1f}mm). 방수용품을 준비하세요.")
        
        if not recommendations:
            recommendations.append("기상 조건이 양호합니다.")
        
        return recommendations
    
    @staticmethod
    def format_analysis_message(analysis: Dict) -> str:
        """분석 결과를 메시지 형식으로 포맷"""
        message = f"📍 *{analysis['site']}* 클라이밍 적합도\n"
        message += f"⏰ {analysis['timestamp'][:16]}\n"
        message += "=" * 40 + "\n\n"
        
        # 종합 평가
        if analysis['summary']:
            summary = analysis['summary']
            message += f"{summary['emoji']} *평가: {analysis['summary']['rating'].upper()}*\n"
            message += f"점수: {summary['average_score']}/100\n"
            message += f"조회 출처: {summary['sources_count']}개 기상 업체\n\n"
        
        # 각 API별 상세 정보
        for source, data in analysis['sources'].items():
            message += f"🔹 *{source}*\n"
            
            weather = data['weather']
            message += f"  온도: {weather.get('temp', 'N/A')}°C\n"
            message += f"  바람: {weather.get('wind_speed', 'N/A')}km/h\n"
            message += f"  습도: {weather.get('humidity', 'N/A')}%\n"
            message += f"  강수확률: {weather.get('rain_1h', 0):.1f}mm\n"
            
            suitability = data['suitability']
            message += f"  적합도: {suitability['score']}/100 ({suitability['emoji']})\n"
            message += "\n"
        
        # 권장사항
        if analysis['sources']:
            first_source = list(analysis['sources'].values())[0]
            recommendations = first_source['recommendations']
            message += f"💡 *권장사항*\n"
            for rec in recommendations:
                message += f"  • {rec}\n"
        
        return message


if __name__ == '__main__':
    # 테스트 코드
    test_weather = {
        'temp': 15,
        'wind_speed': 12,
        'humidity': 65,
        'rain_1h': 0,
        'rain_prob': 20,
        'description': '맑음'
    }
    
    score, rating, penalties = WeatherAnalyzer.calculate_suitability(test_weather)
    print(f"점수: {score}/100")
    print(f"평점: {rating} {WeatherAnalyzer.get_rating_emoji(rating)}")
    print(f"페널티: {penalties}")
    print(f"설명: {WeatherAnalyzer.get_rating_description(rating)}")
