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
# ── 모멘텀형 가중치 (확장 팩터 포함) ──
#   단기 트레이딩 지향: 모멘텀/차트/테마/수혜를 고가중,
#   품질·가치 팩터는 '밸류 트랩 방어' 목적의 보조 지표로 저가중.
#   ※ rumor(호재)는 검증 안 된 고위험이라 안전 신호 아래로 절제.
#
#   group: 표시/그룹핑용. tier: 데이터 가용 단계
#     "live"    = 현재 데이터로 계산됨
#     "data"    = 로직 완성·재무제표 연동 시 자동 작동(현재 available=False)
#     "source"  = 신규 데이터소스 필요(스캐폴드)
CRITERIA = {
    # ── 통계적 모멘텀/차트 (강한 신호, 고가중) ──
    "mom_12_1":     {"label": "중기 모멘텀(12-1)", "weight": 1.3, "horizon": "중기", "group": "통계", "tier": "live"},
    "quant":        {"label": "퀀트·차트 신호",   "weight": 1.1, "horizon": "단기", "group": "통계", "tier": "live"},
    "theme":        {"label": "테마 급부상",      "weight": 1.1, "horizon": "단기", "group": "테마", "tier": "live"},
    "beneficiary":  {"label": "간접 수혜주(리드-래그)", "weight": 1.0, "horizon": "중기", "group": "통계", "tier": "live"},
    # ── 추정치/이벤트 (예측력 높음) ──
    "est_revision": {"label": "추정치 상향·서프라이즈", "weight": 0.9, "horizon": "중기", "group": "이벤트", "tier": "source"},
    "target_gap":   {"label": "목표가 갭",        "weight": 0.7, "horizon": "중기", "group": "이벤트", "tier": "data"},
    "rumor":        {"label": "호재 모멘텀",      "weight": 0.7, "horizon": "단기", "group": "이벤트", "tier": "data"},
    "insider":      {"label": "내부자 군집매수",  "weight": 0.6, "horizon": "중기", "group": "이벤트", "tier": "source"},
    # ── 품질/가치 (밸류 트랩 방어, 보조) ──
    "fscore":       {"label": "퀄리티(F-Score)",  "weight": 0.7, "horizon": "장기", "group": "품질", "tier": "data"},
    "fcf_yield":    {"label": "FCF 수익률",       "weight": 0.6, "horizon": "장기", "group": "품질", "tier": "data"},
    "roic":         {"label": "자본효율(ROIC)",   "weight": 0.6, "horizon": "장기", "group": "품질", "tier": "data"},
    "accruals":     {"label": "발생액 품질",      "weight": 0.5, "horizon": "장기", "group": "품질", "tier": "data"},
    "undervalued":  {"label": "저평가 우량주",    "weight": 0.5, "horizon": "장기", "group": "가치", "tier": "live"},
    "earnings":     {"label": "꾸준한 실적 성장",  "weight": 0.5, "horizon": "장기", "group": "가치", "tier": "live"},
    # ── 정성/국장 특화 ──
    "governance":   {"label": "지배구조·주주환원", "weight": 0.7, "horizon": "중기", "group": "정성", "tier": "source"},
    "blog":         {"label": "신뢰 소스 언급",   "weight": 0.6, "horizon": "중기", "group": "정성", "tier": "data"},
}


# ---------------------------------------------------------------------------
# 결합 방식 (가장 효과 큰 부분): 횡단면 정규화 + 배제 필터 + 리스크 조정
# ---------------------------------------------------------------------------
class Combination:
    # 각 팩터 원점수를 시장 내 횡단면에서 '백분위 순위(0~100)'로 변환 후 가중합.
    #   "percentile" = 백분위 순위(이상치에 강건, 권장)
    #   "zscore"     = 표준화 후 0~100 매핑
    #   "raw"        = (구버전) 원점수 그대로 가중평균
    NORMALIZE = "percentile"

    # 저변동성 이상현상 반영: 최종점수에 (1-λ)·종합 + λ·(저변동성 점수).
    #   변동성이 낮을수록 가점. 0이면 리스크 조정 끔.
    RISK_LAMBDA = 0.15


# ---------------------------------------------------------------------------
# 배제(스크리닝) 필터 — '사는 신호'보다 먼저 적용해 영구적 자본 훼손 회피
# ---------------------------------------------------------------------------
class Exclusion:
    # Altman Z-Score: 이 값 미만이면 부도위험 → 추천에서 제외 (데이터 있을 때만)
    ALTMAN_Z_MIN = 1.8
    # 적신호(감사의견 비적정·잦은 감사인 교체 등) 발견 시 제외
    EXCLUDE_ON_RED_FLAG = True

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

    # ── 확장 팩터 ──
    # 중기 모멘텀(12-1): 이 수익률(%) 이상이면 만점권
    MOM_12_1_STRONG = 40.0
    # 리드-래그: 시차 상관이 이 값 이상이고 best_lag>0이면 '진짜 추종'
    LEADLAG_MIN_CORR = 0.3
    # Piotroski F-Score: 0~9. 이 값 이상이면 우량
    FSCORE_GOOD = 7
    # FCF Yield(%): 이 값 이상이면 만점권
    FCF_YIELD_GOOD = 8.0
    # ROIC - WACC 스프레드(%p): 이 값 이상이면 가치창출 양호
    ROIC_SPREAD_GOOD = 5.0
    # Accruals 비율: 이 값 이상이면 이익의 질 낮음(감점)
    ACCRUALS_BAD = 0.10
    # 추정치 상향(%): 이 값 이상이면 강한 상향 추세
    EST_REVISION_GOOD = 5.0
    # 총주주환원율(%): 이 값 이상이면 주주환원 우수
    PAYOUT_GOOD = 5.0


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
