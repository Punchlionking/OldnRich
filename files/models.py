"""
데이터 모델.

여기 정의된 dataclass들은 "추천 엔진이 종목 하나를 평가하기 위해 필요한
데이터"를 그대로 명세한 것입니다. 즉, 이 모델을 채우려면 API에서 무엇을
가져와야 하는지가 곧바로 드러납니다. (datasources.py 참고)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# 입력 데이터: 종목 하나를 구성하는 원천 데이터들
# ---------------------------------------------------------------------------

@dataclass
class FinancialData:
    """재무/밸류에이션 (기준 #1 저평가, #7 실적성장에 사용)."""
    per: float                  # 주가수익비율
    pbr: float                  # 주가순자산비율
    sector_per: float           # 업종 평균 PER
    sector_pbr: float           # 업종 평균 PBR
    roe: float                  # 자기자본이익률 (%)
    operating_margin: float     # 영업이익률 (%)
    debt_ratio: float           # 부채비율 (%)
    # 분기 시계열 (최근 분기가 [0]). 보통 4~8분기.
    revenue_quarters: list[float] = field(default_factory=list)
    op_income_quarters: list[float] = field(default_factory=list)


@dataclass
class TechData:
    """가격/거래량/기술적지표 (기준 #2, #3, #4에 사용)."""
    current_price: float
    volume: float               # 당일 거래량
    avg_volume_20d: float       # 20일 평균 거래량
    price_change_5d: float      # 최근 5거래일 등락률 (%)
    rsi_14: float               # 14일 RSI (0~100)
    macd: float
    macd_signal: float
    macd_prev_diff: float       # 전일 (macd - signal). 골든크로스 판정용
    bb_position: float          # 볼린저밴드 내 위치 0(하단)~1(상단)
    ma20: float
    ma60: float


@dataclass
class SentimentData:
    """뉴스/감성 (기준 #3 호재 루머에 사용)."""
    news_count_today: int
    avg_news_count: float
    sentiment_score: float      # -1(부정) ~ +1(긍정)
    sentiment_prev: float       # 직전 감성 점수 (스파이크 판정용)


@dataclass
class AnalystData:
    """증권사 컨센서스 (기준 #5 목표가 갭에 사용)."""
    target_mean: float          # 평균 목표가
    num_analysts: int           # 커버 애널리스트 수 (신뢰도 가중)


@dataclass
class ThemeData:
    """테마/섹터 (기준 #2 테마 급부상에 사용)."""
    themes: list[str] = field(default_factory=list)
    theme_volume_surge: float = 1.0   # 동일 테마군 거래량 / 평소 (배수)
    sector_strength_pct: float = 50.0  # 섹터 강도 백분위 0~100 (높을수록 강세)


@dataclass
class BeneficiaryData:
    """간접 수혜 관계 (기준 #6에 사용)."""
    leader_ticker: Optional[str] = None
    leader_change_5d: float = 0.0     # 대장주 5일 등락률 (%)
    own_change_5d: float = 0.0        # 본 종목 5일 등락률 (%)
    correlation: float = 0.0          # 대장주와의 상관계수 (0~1)


@dataclass
class BlogData:
    """신뢰 소스 언급 (기준 #8에 사용)."""
    mention_count_7d: int = 0   # 최근 7일 언급 횟수
    source_count: int = 0       # 언급한 '서로 다른' 신뢰 소스 수
    days_since_last: float = 99.0


@dataclass
class Stock:
    """평가 대상 종목 1개."""
    ticker: str
    name: str
    market: str                 # "KR" | "US"
    currency: str               # "KRW" | "USD"
    financial: FinancialData
    tech: TechData
    sentiment: SentimentData
    analyst: AnalystData
    theme: ThemeData
    beneficiary: BeneficiaryData
    blog: BlogData


# ---------------------------------------------------------------------------
# 출력 데이터: 추천 결과 (앱이 그대로 받아쓰는 형태)
# ---------------------------------------------------------------------------

@dataclass
class CriterionResult:
    """기준 1개에 대한 평가 결과."""
    key: str                    # 기준 식별자 (예: "undervalued")
    label: str                  # 표시용 한글 라벨
    score: float                # 0~100
    horizon: str                # "장기" | "중기" | "단기"
    reason: str                 # 사용자에게 보여줄 추천 이유 문장
    risk: str = "보통"          # "보통" | "높음"
    available: bool = True      # False면 '데이터 없음' → 종합점수 계산에서 제외


@dataclass
class Recommendation:
    """최종 추천 종목 1개 (= 앱의 카드 1장)."""
    ticker: str
    name: str
    market: str
    currency: str
    current_price: float
    overall_score: float
    target_horizon: str         # 대표 타겟 시점
    primary_criterion: str      # 대표 추천 기준 key
    primary_label: str          # 대표 추천 기준 라벨
    risk_level: str             # 종합 위험도
    reasons: list[CriterionResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
