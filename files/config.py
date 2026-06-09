"""
엔진 설정.

- 8개 기준 각각의 라벨, 타겟 시점, 종합점수 가중치
- 점수 계산에 쓰는 임계값들
- API 키 자리 (환경변수에서 읽음)

가중치/임계값은 운영하면서 백테스트로 튜닝하는 것이 정석입니다.
지금 값은 "합리적인 출발점"이며 자유롭게 조정하세요.
"""

import os


# ---------------------------------------------------------------------------
# 8개 기준 메타데이터
#   weight: 종합점수에 합산될 때의 가중치 (합이 1이 아니어도 됨)
#   horizon: 이 기준으로 뽑혔을 때 붙는 타겟 시점
# ---------------------------------------------------------------------------
# ── 모멘텀형 가중치 ──
#   단기 트레이딩 지향: 차트·테마·수혜·호재 신호를 고가중,
#   가치(저평가)·실적은 보조 지표로 저가중.
#   ※ '호재 모멘텀(rumor)'은 검증 안 된 고위험 신호라 모멘텀형에서도
#     안전한 신호(quant·theme) 아래로 절제한다.
CRITERIA = {
    "quant":        {"label": "퀀트·차트 신호",  "weight": 1.3, "horizon": "단기"},  # 모멘텀 핵심
    "theme":        {"label": "테마 급부상",     "weight": 1.2, "horizon": "단기"},  # 테마 급등 포착
    "beneficiary":  {"label": "간접 수혜주",     "weight": 1.1, "horizon": "중기"},  # 대장주 추격
    "target_gap":   {"label": "목표가 갭",       "weight": 0.9, "horizon": "중기"},
    "rumor":        {"label": "호재 모멘텀",     "weight": 0.8, "horizon": "단기"},  # 고위험 → 절제
    "blog":         {"label": "신뢰 소스 언급",  "weight": 0.8, "horizon": "중기"},
    "undervalued":  {"label": "저평가 우량주",   "weight": 0.6, "horizon": "장기"},  # 가치 → 보조
    "earnings":     {"label": "꾸준한 실적 성장", "weight": 0.6, "horizon": "장기"},  # 실적 → 보조
}

# 추천 이유로 채택할 기준의 최소 점수 (이보다 낮으면 카드에 표시 안 함)
REASON_MIN_SCORE = 40.0

# 시장별 추천 종목 수
TOP_N = 5

# 다양성 옵션: 같은 대표기준을 가진 종목이 이 개수를 넘지 않도록 제한
#   (예: 5종목이 전부 '목표가 갭'으로만 뽑히는 것 방지). None이면 순수 점수순.
MAX_PER_PRIMARY = 2

# 고위험으로 분류할 기준들 (앱에서 경고 라벨 표시용)
HIGH_RISK_CRITERIA = {"rumor"}


# ---------------------------------------------------------------------------
# 점수 계산 임계값
# ---------------------------------------------------------------------------
class Thresholds:
    # #1 저평가
    UNDERVALUED_GOOD_ROE = 15.0          # ROE 이 값 이상이면 우량
    UNDERVALUED_GOOD_MARGIN = 10.0       # 영업이익률
    UNDERVALUED_MAX_DEBT = 150.0         # 부채비율 이 값 넘으면 감점

    # #2 테마
    THEME_SURGE_HOT = 2.5                # 테마 거래량 배수 이 이상이면 만점권

    # #3 호재 모멘텀
    RUMOR_VOLUME_SPIKE = 3.0             # 거래량 / 20일평균 이 이상이면 이상치
    RUMOR_MOMENTUM_GOOD = 8.0            # 5일 등락률(%) 기준

    # #4 퀀트
    QUANT_RSI_OVERSOLD = 35.0            # 이하에서 반등 시 매수신호
    QUANT_BB_LOWER = 0.2                 # 볼린저 하단 근접

    # #5 목표가 갭
    TARGET_GAP_GOOD = 0.30               # 상승여력 30% 이상이면 만점권
    TARGET_MIN_ANALYSTS = 3              # 신뢰도 확보 최소 애널리스트 수

    # #6 수혜주
    BENEFICIARY_LEADER_SURGE = 15.0      # 대장주 5일 등락률(%) 기준
    BENEFICIARY_LAG_GOOD = 5.0           # 본 종목이 아직 덜 오른 정도(%p)

    # #7 실적 성장
    EARNINGS_MIN_QUARTERS = 4            # 평가에 필요한 최소 분기 수

    # #8 블로그
    BLOG_HOT_MENTIONS = 5                # 7일 언급수 이 이상이면 강한 신호


# ---------------------------------------------------------------------------
# API 키 (환경변수). 미설정 시 None → 엔진은 자동으로 Mock 데이터로 동작.
# ---------------------------------------------------------------------------
class ApiKeys:
    KIS_APP_KEY = os.environ.get("KIS_APP_KEY")
    KIS_APP_SECRET = os.environ.get("KIS_APP_SECRET")
    DART_API_KEY = os.environ.get("DART_API_KEY")
    ALPHA_VANTAGE = os.environ.get("ALPHA_VANTAGE_KEY")
    TWELVE_DATA = os.environ.get("TWELVE_DATA_KEY")
    FINNHUB = os.environ.get("FINNHUB_KEY")
