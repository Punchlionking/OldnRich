"""
추천 기준 8개의 점수화 로직 (엔진의 핵심).

각 기준은 Stock 1개를 받아 CriterionResult(0~100 점수 + 추천이유 문장)를
반환합니다. 점수 공식은 "해석 가능"하게 설계했습니다 — 즉 왜 이 점수가
나왔는지 사람이 읽고 납득할 수 있고, 그 설명이 그대로 앱의 '추천 이유'가
됩니다.

공식과 임계값은 출발점이며, 실제로는 과거 데이터로 백테스트하여
가중치를 튜닝해야 합니다.
"""

from __future__ import annotations

from .models import Stock, CriterionResult
from .config import CRITERIA, Thresholds as T


# ---------------------------------------------------------------------------
# 작은 헬퍼: 값을 0~100 점수로 선형 매핑
# ---------------------------------------------------------------------------
def _scale(x: float, lo: float, hi: float) -> float:
    """x가 lo면 0점, hi면 100점. 범위 밖은 0/100으로 클램프."""
    if hi == lo:
        return 0.0
    v = (x - lo) / (hi - lo) * 100.0
    return max(0.0, min(100.0, v))


def _result(key: str, score: float, reason: str) -> CriterionResult:
    meta = CRITERIA[key]
    return CriterionResult(
        key=key,
        label=meta["label"],
        score=round(score, 1),
        horizon=meta["horizon"],
        reason=reason,
        risk="높음" if key in {"rumor"} else "보통",
    )


# ---------------------------------------------------------------------------
# #1 저평가 우량주 (장기)
#   - 업종 대비 PER/PBR 할인 + 수익성(ROE,마진) - 부채 페널티
# ---------------------------------------------------------------------------
def score_undervalued(s: Stock) -> CriterionResult:
    f = s.financial
    per_disc = (f.sector_per - f.per) / f.sector_per if f.sector_per else 0.0
    pbr_disc = (f.sector_pbr - f.pbr) / f.sector_pbr if f.sector_pbr else 0.0
    valuation = (per_disc + pbr_disc) / 2.0          # -1..+1 (양수=저평가)

    valuation_score = _scale(valuation, -0.1, 0.5)   # 10% 고평가~50% 저평가
    roe_score = _scale(f.roe, 0, T.UNDERVALUED_GOOD_ROE * 1.5)
    margin_score = _scale(f.operating_margin, 0, T.UNDERVALUED_GOOD_MARGIN * 2)
    debt_penalty = _scale(f.debt_ratio, T.UNDERVALUED_MAX_DEBT, T.UNDERVALUED_MAX_DEBT * 2)

    score = (0.45 * valuation_score + 0.30 * roe_score
             + 0.25 * margin_score - 0.30 * debt_penalty)
    score = max(0.0, score)

    reason = (
        f"업종 평균 PER {f.sector_per:.1f}·PBR {f.sector_pbr:.1f} 대비 "
        f"PER {f.per:.1f}·PBR {f.pbr:.1f}로 {valuation*100:.0f}% 저평가, "
        f"ROE {f.roe:.0f}%·영업이익률 {f.operating_margin:.0f}%로 수익성 양호"
    )
    return _result("undervalued", score, reason)


# ---------------------------------------------------------------------------
# #2 테마 급부상 (단기)
#   - 동일 테마군 거래량 급증 + 섹터 강도
# ---------------------------------------------------------------------------
def score_theme(s: Stock) -> CriterionResult:
    t = s.theme
    surge_score = _scale(t.theme_volume_surge, 1.0, T.THEME_SURGE_HOT)
    strength_score = t.sector_strength_pct          # 이미 0~100 백분위
    score = 0.6 * surge_score + 0.4 * strength_score

    theme_name = t.themes[0] if t.themes else "해당 섹터"
    reason = (
        f"'{theme_name}' 테마 거래량이 평소 대비 {t.theme_volume_surge:.1f}배 급증, "
        f"섹터 강도 상위 {100 - t.sector_strength_pct:.0f}%"
    )
    return _result("theme", score, reason)


# ---------------------------------------------------------------------------
# #3 호재 모멘텀 (단기, 고위험)
#   ※ '루머 추종'이 아니라 '비정상 거래량 + 단기 모멘텀 + 감성 스파이크'로 정의.
#   ※ 검증되지 않은 신호이므로 risk='높음' 고정.
# ---------------------------------------------------------------------------
def score_rumor(s: Stock) -> CriterionResult:
    td, sd = s.tech, s.sentiment
    vol_ratio = td.volume / td.avg_volume_20d if td.avg_volume_20d else 1.0
    vol_score = _scale(vol_ratio, 1.5, T.RUMOR_VOLUME_SPIKE)
    mom_score = _scale(td.price_change_5d, 0, T.RUMOR_MOMENTUM_GOOD * 2)
    sent_spike = sd.sentiment_score - sd.sentiment_prev
    sent_score = _scale(sent_spike, 0, 0.5)
    news_surge = sd.news_count_today / sd.avg_news_count if sd.avg_news_count else 1.0
    news_score = _scale(news_surge, 1.0, 3.0)

    score = 0.4 * vol_score + 0.3 * mom_score + 0.15 * sent_score + 0.15 * news_score

    reason = (
        f"거래량 20일 평균 대비 {vol_ratio:.1f}배, 최근 5일 {td.price_change_5d:+.0f}%, "
        f"뉴스량 {news_surge:.1f}배·감성 급등 — 검증되지 않은 단기 모멘텀(고위험)"
    )
    return _result("rumor", score, reason)


# ---------------------------------------------------------------------------
# #4 퀀트·차트 신호 (단기)
#   - RSI 과매도 반등 + MACD 골든크로스 + 볼린저 하단 지지
# ---------------------------------------------------------------------------
def score_quant(s: Stock) -> CriterionResult:
    td = s.tech
    # RSI: 과매도(<35)에서 50을 향해 반등할수록 좋음. 30 근처가 최고점.
    if td.rsi_14 <= T.QUANT_RSI_OVERSOLD:
        rsi_score = _scale(td.rsi_14, 20, T.QUANT_RSI_OVERSOLD) * -1 + 100
        rsi_score = _scale(35 - td.rsi_14, 0, 15)
    else:
        rsi_score = _scale(50 - td.rsi_14, -20, 15)
    # MACD 골든크로스: 오늘 (macd-signal)>0 이고 어제는 <0 이었으면 강한 신호
    diff_now = td.macd - td.macd_signal
    cross = diff_now > 0 and td.macd_prev_diff <= 0
    macd_score = 100.0 if cross else _scale(diff_now, -1.0, 1.0)
    # 볼린저밴드 하단 지지
    bb_score = _scale(T.QUANT_BB_LOWER - td.bb_position, -0.3, T.QUANT_BB_LOWER)

    score = 0.4 * rsi_score + 0.35 * macd_score + 0.25 * bb_score

    cross_txt = "MACD 골든크로스 발생, " if cross else ""
    reason = (
        f"RSI {td.rsi_14:.0f}{'(과매도 반등)' if td.rsi_14 < 40 else ''}, "
        f"{cross_txt}볼린저밴드 위치 {td.bb_position:.0%}(하단 지지)"
    )
    return _result("quant", score, reason)


# ---------------------------------------------------------------------------
# #5 목표가 갭 (중기)
#   - (평균목표가-현재가)/현재가, 애널리스트 수로 신뢰도 가중
# ---------------------------------------------------------------------------
def score_target_gap(s: Stock) -> CriterionResult:
    a, td = s.analyst, s.tech
    if a.target_mean <= 0 or td.current_price <= 0:
        return _result("target_gap", 0.0, "목표가 데이터 없음")
    upside = (a.target_mean - td.current_price) / td.current_price
    gap_score = _scale(upside, 0.0, T.TARGET_GAP_GOOD)
    # 애널리스트 수가 적으면 신뢰도 할인
    conf = _scale(a.num_analysts, 1, T.TARGET_MIN_ANALYSTS * 2) / 100.0
    score = gap_score * (0.5 + 0.5 * conf)

    reason = (
        f"증권사 평균 목표가 {a.target_mean:,.0f} vs 현재가 {td.current_price:,.0f}, "
        f"상승여력 {upside*100:+.0f}% (애널리스트 {a.num_analysts}명 커버)"
    )
    return _result("target_gap", score, reason)


# ---------------------------------------------------------------------------
# #6 간접 수혜주 (중기)
#   - 대장주는 급등했는데 본 종목은 아직 덜 오른 '갭'을 노림
# ---------------------------------------------------------------------------
def score_beneficiary(s: Stock) -> CriterionResult:
    b = s.beneficiary
    if not b.leader_ticker:
        return _result("beneficiary", 0.0, "연관 대장주 없음")
    leader_score = _scale(b.leader_change_5d, 0, T.BENEFICIARY_LEADER_SURGE * 1.5)
    lag = b.leader_change_5d - b.own_change_5d        # 따라잡을 여지
    lag_score = _scale(lag, 0, T.BENEFICIARY_LEADER_SURGE)
    corr_score = b.correlation * 100.0
    score = 0.35 * leader_score + 0.4 * lag_score + 0.25 * corr_score

    reason = (
        f"연관 대장주 {b.leader_ticker} 최근 5일 {b.leader_change_5d:+.0f}% 급등, "
        f"본 종목은 {b.own_change_5d:+.0f}%에 그쳐 갭 존재 (상관계수 {b.correlation:.2f})"
    )
    return _result("beneficiary", score, reason)


# ---------------------------------------------------------------------------
# #7 꾸준한 실적 성장 (장기)
#   - 연속 증가 분기 수 + 성장의 꾸준함(낮은 변동성)
# ---------------------------------------------------------------------------
def score_earnings(s: Stock) -> CriterionResult:
    f = s.financial
    rev, op = f.revenue_quarters, f.op_income_quarters
    if len(rev) < T.EARNINGS_MIN_QUARTERS or len(op) < T.EARNINGS_MIN_QUARTERS:
        return _result("earnings", 0.0, "실적 시계열 데이터 부족")

    # rev[0]가 최신. 최신→과거로 내려가며 직전 분기보다 컸던 횟수 카운트.
    def consecutive_growth(series: list[float]) -> int:
        cnt = 0
        for i in range(len(series) - 1):
            if series[i] > series[i + 1]:
                cnt += 1
            else:
                break
        return cnt

    rev_streak = consecutive_growth(rev)
    op_streak = consecutive_growth(op)
    streak = min(rev_streak, op_streak)
    streak_score = _scale(streak, 1, len(rev) - 1)

    # YoY 성장률 (4분기 전 대비)
    yoy = 0.0
    if len(rev) >= 5 and rev[4]:
        yoy = (rev[0] - rev[4]) / abs(rev[4])
    yoy_score = _scale(yoy, 0, 0.4)

    score = 0.6 * streak_score + 0.4 * yoy_score
    reason = (
        f"최근 {streak}분기 연속 매출·영업이익 동반 증가"
        + (f", 매출 YoY {yoy*100:+.0f}%" if yoy else "")
    )
    return _result("earnings", score, reason)


# ---------------------------------------------------------------------------
# #8 신뢰 소스 언급 (중기)
#   - 화이트리스트 소스의 최근 언급 빈도 + 소스 다양성 + 최신성
# ---------------------------------------------------------------------------
def score_blog(s: Stock) -> CriterionResult:
    b = s.blog
    if b.mention_count_7d == 0:
        return _result("blog", 0.0, "최근 신뢰 소스 언급 없음")
    freq_score = _scale(b.mention_count_7d, 1, T.BLOG_HOT_MENTIONS)
    diversity_score = _scale(b.source_count, 1, 4)      # 서로 다른 소스 4곳이면 만점
    recency_score = _scale(7 - b.days_since_last, 0, 7)
    score = 0.5 * freq_score + 0.3 * diversity_score + 0.2 * recency_score

    reason = (
        f"신뢰 소스 {b.source_count}곳에서 최근 7일간 {b.mention_count_7d}회 언급 "
        f"(최근 언급 {b.days_since_last:.0f}일 전)"
    )
    return _result("blog", score, reason)


# 모든 기준을 순서대로 실행하는 레지스트리
ALL_CRITERIA = [
    score_undervalued,
    score_theme,
    score_rumor,
    score_quant,
    score_target_gap,
    score_beneficiary,
    score_earnings,
    score_blog,
]


def evaluate_all(stock: Stock) -> list[CriterionResult]:
    """한 종목을 8개 기준으로 모두 평가."""
    return [fn(stock) for fn in ALL_CRITERIA]
