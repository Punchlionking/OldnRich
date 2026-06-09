"""
추천 엔진.

흐름: 종목 리스트 → 각 종목 8기준 평가 → 종합점수 산출 + 대표기준 결정
     → 시장별 상위 N개 선정(다양성 제약) → Recommendation 리스트.
"""

from __future__ import annotations

from .models import Stock, Recommendation, CriterionResult
from .config import CRITERIA, REASON_MIN_SCORE, TOP_N, MAX_PER_PRIMARY, HIGH_RISK_CRITERIA
from .criteria import evaluate_all


def _overall_score(results: list[CriterionResult]) -> float:
    """기준별 점수를 가중 합산해 0~100 종합점수로 환산.

    데이터가 없는 기준(available=False)은 분자·분모 모두에서 제외한다.
    → '데이터가 없을 뿐'인 기준이 0점으로 종합점수를 끌어내리는 것을 방지.
    """
    usable = [r for r in results if r.available]
    total_w = sum(CRITERIA[r.key]["weight"] for r in usable)
    if total_w == 0:
        return 0.0
    weighted = sum(r.score * CRITERIA[r.key]["weight"] for r in usable)
    return round(weighted / total_w, 1)


def _build_recommendation(stock: Stock) -> Recommendation:
    results = evaluate_all(stock)

    # 대표 기준은 '데이터 있는' 기준 중에서만 고름.
    usable = [r for r in results if r.available] or results
    # 가중치를 반영한 '대표 기준' = (점수 × 가중치)가 가장 큰 기준
    primary = max(usable, key=lambda r: r.score * CRITERIA[r.key]["weight"])

    # 카드에 보여줄 추천 이유: 대표기준을 맨 앞에 고정하고,
    # 나머지는 임계점 이상이고 데이터 있는 기준만 점수 높은 순으로 뒤에 붙임.
    others = sorted(
        [r for r in results
         if r.available and r.score >= REASON_MIN_SCORE and r.key != primary.key],
        key=lambda r: r.score,
        reverse=True,
    )
    reasons = [primary] + others

    # 종합 위험도: 대표기준이 고위험군이면 '높음'
    risk_level = "높음" if primary.key in HIGH_RISK_CRITERIA else "보통"

    price = stock.tech.current_price
    price = round(price) if stock.currency == "KRW" else round(price, 2)

    return Recommendation(
        ticker=stock.ticker,
        name=stock.name,
        market=stock.market,
        currency=stock.currency,
        current_price=price,
        overall_score=_overall_score(results),
        target_horizon=primary.horizon,
        primary_criterion=primary.key,
        primary_label=primary.label,
        risk_level=risk_level,
        reasons=reasons,
    )


def _select_with_diversity(recs: list[Recommendation], top_n: int,
                           max_per_primary: int | None) -> list[Recommendation]:
    """점수순 정렬 후, 같은 대표기준이 max_per_primary를 넘지 않게 선정."""
    recs_sorted = sorted(recs, key=lambda r: r.overall_score, reverse=True)
    if max_per_primary is None:
        return recs_sorted[:top_n]

    selected: list[Recommendation] = []
    counts: dict[str, int] = {}
    leftovers: list[Recommendation] = []
    for r in recs_sorted:
        if len(selected) >= top_n:
            break
        if counts.get(r.primary_criterion, 0) < max_per_primary:
            selected.append(r)
            counts[r.primary_criterion] = counts.get(r.primary_criterion, 0) + 1
        else:
            leftovers.append(r)
    # 다양성 제약 때문에 자리가 남으면 점수순으로 채움
    for r in leftovers:
        if len(selected) >= top_n:
            break
        selected.append(r)
    return selected[:top_n]


def recommend(stocks: list[Stock],
              top_n: int = TOP_N,
              max_per_primary: int | None = MAX_PER_PRIMARY) -> dict[str, list[Recommendation]]:
    """전체 유니버스를 평가해 시장(KR/US)별 추천 리스트를 반환."""
    by_market: dict[str, list[Recommendation]] = {"KR": [], "US": []}
    for s in stocks:
        rec = _build_recommendation(s)
        by_market.setdefault(s.market, []).append(rec)

    return {
        market: _select_with_diversity(recs, top_n, max_per_primary)
        for market, recs in by_market.items()
    }
