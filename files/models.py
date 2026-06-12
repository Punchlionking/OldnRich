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
    # 통계적 팩터 (데이터 충분 시 채움. None=계산 불가)
    mom_12_1: Optional[float] = None    # 크로스섹션 모멘텀(12-1개월) 수익률(%)
    volatility: Optional[float] = None  # 연율화 변동성(%) — 저변동성 리스크조정용
    closes: list[float] = field(default_factory=list)  # 일봉 종가(과거→최신). 리드-래그용


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
    # 리드-래그 (그레인저 인과 프록시): best_lag>0 & corr 높음 = '진짜 시차 추종'
    lead_lag_days: int = 0            # 대장주를 며칠 시차로 따라가는지
    lead_lag_corr: float = 0.0        # 그 시차에서의 상관


@dataclass
class BlogData:
    """신뢰 소스 언급 (기준 #8에 사용)."""
    mention_count_7d: int = 0   # 최근 7일 언급 횟수
    source_count: int = 0       # 언급한 '서로 다른' 신뢰 소스 수
    days_since_last: float = 99.0


@dataclass
class QualityData:
    """
    펀더멘털 품질·통계 팩터 입력 (Optional = None이면 '데이터 없음' → 해당 팩터 제외).

    재무제표(손익/재무상태/현금흐름)에서 산출. DART(국장)·Alpha Vantage/FMP(미장)
    연동 시 채워집니다. 단위는 절대값(통화 무관, 비율 계산에만 쓰임).
    """
    # ── Piotroski F-Score 9개 항목 입력 ──
    roa: Optional[float] = None              # 총자산이익률(%)
    roa_prev: Optional[float] = None         # 전년 ROA
    cfo: Optional[float] = None              # 영업활동현금흐름
    net_income: Optional[float] = None       # 당기순이익
    leverage: Optional[float] = None         # 장기부채/총자산
    leverage_prev: Optional[float] = None
    current_ratio: Optional[float] = None    # 유동비율
    current_ratio_prev: Optional[float] = None
    shares_out: Optional[float] = None       # 발행주식수
    shares_out_prev: Optional[float] = None
    gross_margin: Optional[float] = None     # 매출총이익률(%)
    gross_margin_prev: Optional[float] = None
    asset_turnover: Optional[float] = None   # 총자산회전율
    asset_turnover_prev: Optional[float] = None
    # ── FCF Yield ──
    fcf: Optional[float] = None              # 잉여현금흐름 = CFO - CapEx
    market_cap: Optional[float] = None       # 시가총액
    enterprise_value: Optional[float] = None # EV (선택)
    # ── ROIC vs WACC ──
    nopat: Optional[float] = None            # 세후영업이익
    invested_capital: Optional[float] = None # 투하자본
    wacc: Optional[float] = None             # 가중평균자본비용(%)
    # ── Altman Z-Score (부도위험 배제 필터) ──
    working_capital: Optional[float] = None  # 순운전자본
    retained_earnings: Optional[float] = None
    ebit: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    sales: Optional[float] = None
    # ── Accruals 품질 ──
    total_accruals: Optional[float] = None   # (순이익 - CFO) / 총자산. 높을수록 나쁨


@dataclass
class AnalystExtData:
    """이익 추정치 추세 & 어닝 서프라이즈 (PEAD). 신규 소스 필요 시 채움."""
    estimate_revision_pct: Optional[float] = None  # 최근 90일 EPS 추정치 변화율(%)
    earnings_surprise_pct: Optional[float] = None  # 직전 실적의 컨센서스 상회율(%)
    days_since_earnings: Optional[float] = None     # 실적발표 후 경과일(PEAD 창)


@dataclass
class GovernanceData:
    """지배구조·주주환원 (국장 핵심). DART 배당/자사주/밸류업 공시로 정량화."""
    total_payout_ratio: Optional[float] = None     # 총주주환원율(배당+자사주소각)(%)
    buyback_cancel: Optional[bool] = None          # 자사주 소각 여부
    valueup_enrolled: Optional[bool] = None        # 밸류업 프로그램 편입
    governance_score: Optional[float] = None       # 지배구조 점수(0~100, 외부평가)


@dataclass
class InsiderData:
    """내부자 거래 (임원·주요주주 군집 매수). DART 지분변동 / SEC Form4."""
    net_insider_buy_90d: Optional[float] = None    # 90일 순매수 금액(양수=매수우위)
    buyer_count_90d: Optional[int] = None           # 매수에 참여한 내부자 수


@dataclass
class RedFlagData:
    """포렌식 적신호 (배제용). 감사의견·감사인교체·특수관계자거래 등."""
    auditor_changed: Optional[bool] = None          # 잦은 감사인 교체
    audit_opinion_adverse: Optional[bool] = None    # 비적정 감사의견
    related_party_anomaly: Optional[bool] = None     # 비정상 특수관계자 거래


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
    # 고급 팩터 입력 (없으면 기본값 → 해당 팩터 자동 제외)
    quality: QualityData = field(default_factory=QualityData)
    analyst_ext: AnalystExtData = field(default_factory=AnalystExtData)
    governance: GovernanceData = field(default_factory=GovernanceData)
    insider: InsiderData = field(default_factory=InsiderData)
    red_flag: RedFlagData = field(default_factory=RedFlagData)


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
    pick_type: str = "core"     # "core"(우량 추천) | "longtail"(신흥 강자, 고위험)
    reasons: list[CriterionResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
