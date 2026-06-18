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
from .config import CRITERIA, Thresholds as T, Exclusion


# ---------------------------------------------------------------------------
# 작은 헬퍼: 값을 0~100 점수로 선형 매핑
# ---------------------------------------------------------------------------
def _scale(x: float, lo: float, hi: float) -> float:
    """x가 lo면 0점, hi면 100점. 범위 밖은 0/100으로 클램프."""
    if hi == lo:
        return 0.0
    v = (x - lo) / (hi - lo) * 100.0
    return max(0.0, min(100.0, v))


def _result(key: str, score: float, reason: str,
            available: bool = True) -> CriterionResult:
    meta = CRITERIA[key]
    return CriterionResult(
        key=key,
        label=meta["label"],
        score=round(score, 1),
        horizon=meta["horizon"],
        reason=reason,
        risk="높음" if key in {"rumor"} else "보통",
        available=available,
    )


# ---------------------------------------------------------------------------
# #1 저평가 우량주 (장기)
#   - 업종 대비 PER/PBR 할인 + 수익성(ROE,마진) - 부채 페널티
# ---------------------------------------------------------------------------
def score_undervalued(s: Stock) -> CriterionResult:
    f = s.financial
    # PER/PBR이 없거나(0=데이터 미수집) 적자(음수 PER)면 '저평가' 판단 불가 → 제외.
    #   (적자 기업의 음수 PER을 '초저평가'로 오판하던 버그 방지)
    if f.per <= 0 or f.pbr <= 0 or f.sector_per <= 0 or f.sector_pbr <= 0:
        return _result("undervalued", 0.0, "PER/PBR 데이터 없음 또는 적자", available=False)

    per_disc = (f.sector_per - f.per) / f.sector_per
    pbr_disc = (f.sector_pbr - f.pbr) / f.sector_pbr
    valuation = (per_disc + pbr_disc) / 2.0          # -1..+1 (양수=저평가)

    valuation_score = _scale(valuation, -0.1, 0.5)   # 10% 고평가~50% 저평가
    roe_score = _scale(f.roe, 0, T.UNDERVALUED_GOOD_ROE * 1.5)
    margin_score = _scale(f.operating_margin, 0, T.UNDERVALUED_GOOD_MARGIN * 2)
    debt_penalty = _scale(f.debt_ratio, T.UNDERVALUED_MAX_DEBT, T.UNDERVALUED_MAX_DEBT * 2)

    score = (0.45 * valuation_score + 0.30 * roe_score
             + 0.25 * margin_score - 0.30 * debt_penalty)
    score = max(0.0, score)

    # 수익성 코멘트는 실제 값에 따라
    if f.roe > 0 and f.operating_margin > 0:
        prof = f"ROE {f.roe:.0f}%·영업이익률 {f.operating_margin:.0f}%로 수익성 양호"
    elif f.roe == 0 and f.operating_margin == 0:
        prof = "수익성 지표 미수집"
    else:
        prof = f"ROE {f.roe:.0f}%·영업이익률 {f.operating_margin:.0f}%(수익성 부진)"
    disc = max(0.0, valuation) * 100
    reason = (
        f"업종 평균 PER {f.sector_per:.1f}·PBR {f.sector_pbr:.1f} 대비 "
        f"PER {f.per:.1f}·PBR {f.pbr:.1f}로 {disc:.0f}% 저평가, {prof}"
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
    # 데이터소스가 중립 기본값(surge=1.0, strength=50)으로 채운 경우 = 실데이터 없음
    available = not (t.theme_volume_surge <= 1.0 and abs(t.sector_strength_pct - 50.0) < 1e-6)
    if not available:
        reason = "테마 거래량·섹터 강도 데이터 없음"
    return _result("theme", score, reason, available=available)


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
    # 뉴스·감성 데이터가 전혀 없으면(중립 기본값) 호재 모멘텀으로 보기 어려움 → 제외
    no_signal = (sd.sentiment_score == 0.0 and sd.sentiment_prev == 0.0
                 and sd.news_count_today == 0)
    if no_signal:
        reason = "뉴스·감성 데이터 없음"
    return _result("rumor", score, reason, available=not no_signal)


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
        return _result("target_gap", 0.0, "목표가 데이터 없음", available=False)
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
    """대장주 급등 + 본 종목 미반영 갭 + '리드-래그(시차 추종)' 검증.

    단순 동시점 상관은 우연의 동조를 잡을 위험이 커서, 시차 상관(lead_lag)으로
    '대장주를 며칠 시차를 두고 따라가는지'를 함께 본다.
    """
    b = s.beneficiary
    if not b.leader_ticker:
        return _result("beneficiary", 0.0, "연관 대장주 없음", available=False)
    leader_score = _scale(b.leader_change_5d, 0, T.BENEFICIARY_LEADER_SURGE * 1.5)
    lag = b.leader_change_5d - b.own_change_5d        # 따라잡을 여지
    lag_score = _scale(lag, 0, T.BENEFICIARY_LEADER_SURGE)

    # 리드-래그: best_lag>0 이고 시차 상관이 임계 이상이면 '진짜 추종'으로 가점.
    has_leadlag = b.lead_lag_days > 0 and b.lead_lag_corr >= T.LEADLAG_MIN_CORR
    ll_score = _scale(b.lead_lag_corr, T.LEADLAG_MIN_CORR, 0.8) if has_leadlag else \
        b.correlation * 60.0   # 시차관계 없으면 동시점 상관을 약하게만 인정
    score = 0.3 * leader_score + 0.35 * lag_score + 0.35 * ll_score

    if has_leadlag:
        rel = f"대장주를 약 {b.lead_lag_days}일 시차로 추종(시차상관 {b.lead_lag_corr:.2f})"
    else:
        rel = f"동시점 상관 {b.correlation:.2f}(시차 추종관계 약함)"
    leader_disp = b.leader_name or b.leader_ticker
    reason = (
        f"연관 대장주 {leader_disp} 최근 5일 {b.leader_change_5d:+.0f}% 급등, "
        f"본 종목은 {b.own_change_5d:+.0f}%에 그쳐 갭 존재 — {rel}"
    )
    return _result("beneficiary", score, reason)


# ---------------------------------------------------------------------------
# #9 중기 모멘텀 (12-1개월) — 통계적으로 가장 강건한 모멘텀 팩터 (LIVE)
# ---------------------------------------------------------------------------
def score_mom_12_1(s: Stock) -> CriterionResult:
    m = s.tech.mom_12_1
    if m is None:
        return _result("mom_12_1", 0.0, "12개월 가격 데이터 부족", available=False)
    score = _scale(m, -10.0, T.MOM_12_1_STRONG)
    reason = (
        f"최근 1개월 제외 과거 12개월 수익률 {m:+.0f}% "
        f"— 학술적으로 검증된 중기 모멘텀 팩터"
    )
    return _result("mom_12_1", score, reason)


# ---------------------------------------------------------------------------
# #10 퀄리티 종합점수 — Piotroski F-Score (0~9) [데이터 연동 시 작동]
# ---------------------------------------------------------------------------
def score_fscore(s: Stock) -> CriterionResult:
    q = s.quality

    def gt(a, b):   # a,b 중 None 있으면 평가 불가(None) 반환
        return None if (a is None or b is None) else (a > b)

    # 9개 항목 (평가 불가 항목은 None → 채점에서 제외하고 비율로 환산)
    items = [
        (q.roa is not None) and (q.roa > 0),                 # 1 수익성
        (q.cfo is not None) and (q.cfo > 0),                 # 2 영업현금흐름
        gt(q.roa, q.roa_prev),                               # 3 ROA 개선
        gt(q.cfo, q.net_income),                             # 4 현금이익질(낮은 발생액)
        gt(q.leverage_prev, q.leverage),                     # 5 부채 감소(전기>당기)
        gt(q.current_ratio, q.current_ratio_prev),           # 6 유동성 개선
        gt(q.shares_out_prev, q.shares_out)                  # 7 미증자(전기>=당기)
            if (q.shares_out is not None and q.shares_out_prev is not None) else None,
        gt(q.gross_margin, q.gross_margin_prev),             # 8 마진 개선
        gt(q.asset_turnover, q.asset_turnover_prev),         # 9 효율 개선
    ]
    evaluable = [bool(x) for x in items if x is not None]
    if len(evaluable) < 5:
        return _result("fscore", 0.0, "재무제표(F-Score) 데이터 미연동", available=False)

    pts = sum(1 for x in evaluable if x)
    n = len(evaluable)
    pts9 = round(pts / n * 9)                # 9점 만점 환산(평가 가능 항목 기준)
    score = _scale(pts9, 3, 9)
    note = "우량" if pts9 >= T.FSCORE_GOOD else "보통" if pts9 >= 4 else "부실 주의"
    suffix = "" if n == 9 else f" (평가 {n}개 항목 환산)"
    reason = (
        f"Piotroski F-Score {pts9}/9 (수익성·재무건전성·영업효율 종합) — {note}{suffix}"
    )
    return _result("fscore", score, reason)


# ---------------------------------------------------------------------------
# #11 FCF 수익률 — 이익보다 조작 어려운 현금흐름 기반 밸류 [데이터 연동 시]
# ---------------------------------------------------------------------------
def score_fcf_yield(s: Stock) -> CriterionResult:
    q = s.quality
    if q.fcf is None or not q.market_cap:
        return _result("fcf_yield", 0.0, "현금흐름·시총(FCF) 데이터 미연동", available=False)
    base = q.enterprise_value if q.enterprise_value else q.market_cap
    if base <= 0:
        return _result("fcf_yield", 0.0, "FCF 기준 분모 오류", available=False)
    fcf_yield = q.fcf / base * 100.0
    score = _scale(fcf_yield, 0.0, T.FCF_YIELD_GOOD)
    reason = (
        f"FCF 수익률 {fcf_yield:.1f}% (잉여현금흐름/기업가치) "
        f"— 회계조정에 강건한 현금 기반 밸류"
    )
    return _result("fcf_yield", score, reason)


# ---------------------------------------------------------------------------
# #12 자본효율 — ROIC vs WACC [데이터 연동 시]
# ---------------------------------------------------------------------------
def score_roic(s: Stock) -> CriterionResult:
    q = s.quality
    if q.nopat is None or not q.invested_capital or q.wacc is None:
        return _result("roic", 0.0, "ROIC/WACC 데이터 미연동", available=False)
    roic = q.nopat / q.invested_capital * 100.0
    spread = roic - q.wacc
    score = _scale(spread, -5.0, T.ROIC_SPREAD_GOOD * 2)
    reason = (
        f"ROIC {roic:.1f}% vs WACC {q.wacc:.1f}% → 스프레드 {spread:+.1f}%p "
        f"({'가치창출' if spread > 0 else '가치훼손'}) — 부채 레버리지에 안 휘둘리는 효율 지표"
    )
    return _result("roic", score, reason)


# ---------------------------------------------------------------------------
# #13 발생액 품질 — 이익 대비 비현금 발생액 비중(높을수록 나쁨) [데이터 연동 시]
# ---------------------------------------------------------------------------
def score_accruals(s: Stock) -> CriterionResult:
    q = s.quality
    if q.total_accruals is None:
        # net_income, cfo, total_assets 로 직접 계산 시도
        if q.net_income is not None and q.cfo is not None and q.total_assets:
            accr = (q.net_income - q.cfo) / q.total_assets
        else:
            return _result("accruals", 0.0, "발생액 데이터 미연동", available=False)
    else:
        accr = q.total_accruals
    # 발생액이 낮을수록(현금이익질 높을수록) 고득점
    score = _scale(-accr, -T.ACCRUALS_BAD, T.ACCRUALS_BAD)
    reason = (
        f"발생액 비율 {accr:+.2f} "
        f"({'현금흐름이 이익을 뒷받침' if accr < 0.05 else '이익 대비 현금 부족 주의'}) "
        f"— Sloan 발생액 이상현상 필터"
    )
    return _result("accruals", score, reason)


# ---------------------------------------------------------------------------
# #14 추정치 상향 & 어닝 서프라이즈 (PEAD) [신규 소스 필요]
# ---------------------------------------------------------------------------
def score_est_revision(s: Stock) -> CriterionResult:
    e = s.analyst_ext
    if e.estimate_revision_pct is None and e.earnings_surprise_pct is None:
        return _result("est_revision", 0.0,
                       "추정치 시계열·서프라이즈 소스 미연동(Finnhub/FnGuide)", available=False)
    rev = e.estimate_revision_pct or 0.0
    surp = e.earnings_surprise_pct or 0.0
    rev_score = _scale(rev, -2.0, T.EST_REVISION_GOOD)
    surp_score = _scale(surp, 0.0, 10.0)

    # PEAD 감쇠: 어닝 서프라이즈의 표류 효과는 발표 후 ~45일 강하고 이후 약화.
    days = e.days_since_earnings
    decay = 1.0
    if days is not None:
        if days <= 45:
            decay = 1.0
        elif days >= 120:
            decay = 0.2
        else:
            decay = 1.0 - 0.8 * (days - 45) / 75.0
    surp_score *= decay

    score = 0.55 * rev_score + 0.45 * surp_score
    drift = ""
    if surp and days is not None and days <= 60:
        drift = f" (발표 {days:.0f}일 경과, 표류 유효구간)"
    reason = (
        f"애널리스트 강세 비중 {rev:+.1f}%p 변화"
        + (f", 직전 실적 컨센서스 {surp:+.1f}% 상회{drift}" if surp else "")
        + " — 목표가 '수준'보다 예측력 높은 '방향' 신호(PEAD)"
    )
    return _result("est_revision", score, reason)


# ---------------------------------------------------------------------------
# #15 지배구조·주주환원 (국장 핵심, 코리아 디스카운트 해소) [신규 소스 필요]
# ---------------------------------------------------------------------------
def score_governance(s: Stock) -> CriterionResult:
    g = s.governance
    if g.total_payout_ratio is None and g.valueup_enrolled is None:
        return _result("governance", 0.0,
                       "DART 배당·자사주·밸류업 공시 미연동", available=False)
    payout = g.total_payout_ratio or 0.0
    # 배당성향/총주주환원율은 0~50%대 → PAYOUT_GOOD(=30%)에서 만점권
    payout_score = _scale(payout, 0.0, T.PAYOUT_GOOD * 1.6)
    bonus = (25 if g.buyback_cancel else 0) + (20 if g.valueup_enrolled else 0)
    gov = g.governance_score if g.governance_score is not None else 50.0
    score = min(100.0, 0.55 * payout_score + 0.15 * gov + bonus)
    tags = []
    if g.valueup_enrolled:
        tags.append("밸류업 편입")
    if g.buyback_cancel:
        tags.append("자사주 소각")
    reason = (
        f"총주주환원율 {payout:.1f}%"
        + (f", {', '.join(tags)}" if tags else "")
        + " — 리레이팅 직접 트리거(코리아 디스카운트 해소)"
    )
    return _result("governance", score, reason)


# ---------------------------------------------------------------------------
# #16 내부자 군집매수 [신규 소스 필요]
# ---------------------------------------------------------------------------
def score_insider(s: Stock) -> CriterionResult:
    ins = s.insider
    if ins.net_insider_buy_90d is None:
        return _result("insider", 0.0,
                       "내부자 거래(DART 지분변동/SEC Form4) 미연동", available=False)
    if ins.net_insider_buy_90d <= 0:
        return _result("insider", 20.0, "최근 90일 내부자 순매도/중립", available=True)
    buyers = ins.buyer_count_90d or 1
    score = min(100.0, 40.0 + buyers * 15.0)   # 매수 내부자 많을수록 강한 신호
    reason = f"최근 90일 내부자 {buyers}명 군집 매수(순매수 우위) — 긍정 신호"
    return _result("insider", score, reason)


# ---------------------------------------------------------------------------
# Altman Z-Score — 부도위험 '배제 필터' (매수신호 아님)
#   반환: (z_score 또는 None, 데이터유무)
# ---------------------------------------------------------------------------
def altman_z(s: Stock) -> float | None:
    q = s.quality
    needed = [q.working_capital, q.retained_earnings, q.ebit,
              q.total_assets, q.total_liabilities, q.sales, q.market_cap]
    if any(v is None for v in needed) or q.total_assets <= 0 or q.total_liabilities <= 0:
        return None
    ta, tl = q.total_assets, q.total_liabilities
    z = (1.2 * (q.working_capital / ta)
         + 1.4 * (q.retained_earnings / ta)
         + 3.3 * (q.ebit / ta)
         + 0.6 * (q.market_cap / tl)
         + 1.0 * (q.sales / ta))
    return z


# ---------------------------------------------------------------------------
# #7 꾸준한 실적 성장 (장기)
#   - 연속 증가 분기 수 + 성장의 꾸준함(낮은 변동성)
# ---------------------------------------------------------------------------
def score_earnings(s: Stock) -> CriterionResult:
    f = s.financial
    rev, op = f.revenue_quarters, f.op_income_quarters
    if len(rev) < T.EARNINGS_MIN_QUARTERS or len(op) < T.EARNINGS_MIN_QUARTERS:
        return _result("earnings", 0.0, "실적 시계열 데이터 부족", available=False)

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
        return _result("blog", 0.0, "최근 신뢰 소스 언급 없음", available=False)
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
    # 통계/모멘텀
    score_mom_12_1,
    score_quant,
    score_theme,
    score_beneficiary,
    # 이벤트
    score_est_revision,
    score_target_gap,
    score_rumor,
    score_insider,
    # 품질/가치
    score_fscore,
    score_fcf_yield,
    score_roic,
    score_accruals,
    score_undervalued,
    score_earnings,
    # 정성
    score_governance,
    score_blog,
]


def evaluate_all(stock: Stock) -> list[CriterionResult]:
    """한 종목을 모든 기준으로 평가."""
    return [fn(stock) for fn in ALL_CRITERIA]
