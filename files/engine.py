"""
추천 엔진 (v2 — 퀀트 결합 파이프라인).

흐름(시장별):
  1) 평가:   각 종목을 모든 기준으로 채점 (criteria.evaluate_all)
  2) 배제:   Altman Z-Score·적신호로 부도위험/부실 종목 제외 (Exclusion)
  3) 정규화: 각 팩터 원점수를 '시장 내 횡단면 백분위 순위(0~100)'로 변환
             → 단위·스케일이 다른 지표를 공정하게 결합, 이상치에 강건
  4) 결합:   가중 백분위 합 = 종합점수
  5) 리스크조정: 저변동성 종목에 가점 (저변동성 이상현상)
  6) 선정:   다양성 제약 하에 시장별 상위 N개

핵심 개선: "사는 신호를 더 많이 더하기"가 아니라 "배제 → 횡단면 정규화 →
리스크 조정 랭킹" 파이프라인으로 결합 방식 자체를 업그레이드.
"""

from __future__ import annotations

from .models import Stock, Recommendation, CriterionResult
from .config import (
    CRITERIA, REASON_MIN_SCORE, TOP_N, MAX_PER_PRIMARY,
    HIGH_RISK_CRITERIA, Combination, Exclusion, Thresholds as T,
)
from .criteria import evaluate_all, altman_z


# ---------------------------------------------------------------------------
# 횡단면 정규화 유틸
# ---------------------------------------------------------------------------
def _percentile_ranks(values: list[float]) -> list[float]:
    """리스트의 각 원소를 0~100 백분위 순위로 변환 (동률은 평균 순위)."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [50.0]
    ranks = []
    for v in values:
        less = sum(1 for x in values if x < v)
        equal = sum(1 for x in values if x == v)
        ranks.append((less + 0.5 * equal) / n * 100.0)
    return ranks


def _normalize_cross_section(per_stock: list[list[CriterionResult]]
                             ) -> list[dict[str, float]]:
    """
    종목별 기준점수를 '기준별 횡단면 백분위'로 변환.
    반환: 종목 인덱스별 {criterion_key: 정규화점수(0~100)} (available한 것만).
    """
    mode = Combination.NORMALIZE
    # 기준 key별로 (종목idx, 원점수) 수집 (available한 것만)
    by_key: dict[str, list[tuple[int, float]]] = {}
    for i, results in enumerate(per_stock):
        for r in results:
            if r.available:
                by_key.setdefault(r.key, []).append((i, r.score))

    out: list[dict[str, float]] = [dict() for _ in per_stock]
    for key, pairs in by_key.items():
        scores = [s for _, s in pairs]
        if mode == "raw":
            norm = scores
        elif mode == "zscore":
            n = len(scores)
            mean = sum(scores) / n
            var = sum((x - mean) ** 2 for x in scores) / n if n else 0.0
            std = var ** 0.5
            # z를 0~100으로: 평균50, ±2σ를 0/100에 매핑
            norm = [max(0.0, min(100.0, 50.0 + (25.0 * (x - mean) / std))) if std > 0 else 50.0
                    for x in scores]
        else:  # percentile (기본)
            norm = _percentile_ranks(scores)
        for (i, _), nv in zip(pairs, norm):
            out[i][key] = nv
    return out


# ---------------------------------------------------------------------------
# 배제 필터
# ---------------------------------------------------------------------------
def _excluded(stock: Stock) -> str | None:
    """배제 사유 문자열 또는 None. (데이터 있을 때만 작동)"""
    z = altman_z(stock)
    if z is not None and z < Exclusion.ALTMAN_Z_MIN:
        return f"Altman Z {z:.2f} < {Exclusion.ALTMAN_Z_MIN} (부도위험)"
    if Exclusion.EXCLUDE_ON_RED_FLAG:
        rf = stock.red_flag
        if rf.audit_opinion_adverse:
            return "감사의견 비적정"
        if rf.auditor_changed:
            return "잦은 감사인 교체"
        if rf.related_party_anomaly:
            return "비정상 특수관계자 거래"
    return None


# ---------------------------------------------------------------------------
# 종합점수 + 추천 객체 생성
# ---------------------------------------------------------------------------
def _weight_of(key: str, overrides: dict | None) -> float:
    """가중치: 부분 오버라이드(overrides)에 있으면 그 값, 없으면 CRITERIA 기본값."""
    if overrides and key in overrides:
        return overrides[key]
    return CRITERIA[key]["weight"]


def _composite(norm: dict[str, float], weights: dict | None) -> float:
    """정규화점수의 가중 합 → 0~100."""
    if not norm:
        return 0.0
    total_w = sum(_weight_of(k, weights) for k in norm)
    if total_w == 0:
        return 0.0
    weighted = sum(v * _weight_of(k, weights) for k, v in norm.items())
    return weighted / total_w


def _build_recommendation(stock: Stock, results: list[CriterionResult],
                          norm: dict[str, float], final_score: float,
                          weights: dict | None, pick_type: str) -> Recommendation:
    # 대표 기준 = (정규화점수 × 가중치)가 가장 큰 available 기준
    if norm:
        primary_key = max(norm, key=lambda k: norm[k] * _weight_of(k, weights))
    else:
        primary_key = results[0].key
    primary = next(r for r in results if r.key == primary_key)

    others = sorted(
        [r for r in results
         if r.available and r.score >= REASON_MIN_SCORE and r.key != primary_key],
        key=lambda r: norm.get(r.key, r.score), reverse=True,
    )
    reasons = [primary] + others

    # 롱테일은 본질적으로 고위험
    risk_level = "높음" if (pick_type == "longtail" or primary_key in HIGH_RISK_CRITERIA) else "보통"
    price = stock.tech.current_price
    price = round(price) if stock.currency == "KRW" else round(price, 2)

    return Recommendation(
        ticker=stock.ticker, name=stock.name, market=stock.market,
        currency=stock.currency, current_price=price,
        overall_score=round(final_score, 1),
        target_horizon=primary.horizon,
        primary_criterion=primary_key, primary_label=primary.label,
        risk_level=risk_level, pick_type=pick_type, reasons=reasons,
    )


# ---------------------------------------------------------------------------
# 다양성 선정
# ---------------------------------------------------------------------------
def _select_with_diversity(recs: list[Recommendation], top_n: int,
                           max_per_primary: int | None) -> list[Recommendation]:
    recs_sorted = sorted(recs, key=lambda r: r.overall_score, reverse=True)
    if max_per_primary is None:
        return recs_sorted[:top_n]
    selected, counts, leftovers = [], {}, []
    for r in recs_sorted:
        if len(selected) >= top_n:
            break
        if counts.get(r.primary_criterion, 0) < max_per_primary:
            selected.append(r)
            counts[r.primary_criterion] = counts.get(r.primary_criterion, 0) + 1
        else:
            leftovers.append(r)
    for r in leftovers:
        if len(selected) >= top_n:
            break
        selected.append(r)
    return selected[:top_n]


# ---------------------------------------------------------------------------
# 시장 단위 파이프라인
# ---------------------------------------------------------------------------
def _recommend_market(stocks: list[Stock], top_n: int,
                      max_per_primary: int | None,
                      weights: dict | None = None,
                      apply_exclusion: bool = True,
                      pick_type: str = "core") -> list[Recommendation]:
    # 1) 배제 필터 (롱테일은 완화: Altman Z 배제 생략, 적신호는 유지)
    if apply_exclusion:
        survivors = [s for s in stocks if _excluded(s) is None]
    else:
        survivors = list(stocks)
    if not survivors:
        survivors = stocks  # 전부 배제되면(데이터 부족) 원본 유지

    # 2) 평가
    per_stock = [evaluate_all(s) for s in survivors]

    # 3) 횡단면 정규화
    norms = _normalize_cross_section(per_stock)

    # 4) 결합 + 5) 리스크 조정
    vols = [s.tech.volatility for s in survivors]
    have_vol = [v for v in vols if v is not None]
    vol_pct_map: dict[int, float] = {}
    if have_vol:
        idxs = [i for i, v in enumerate(vols) if v is not None]
        pr = _percentile_ranks([vols[i] for i in idxs])
        for i, p in zip(idxs, pr):
            vol_pct_map[i] = p

    # 롱테일은 변동성 가점을 끄거나 줄임(고변동성 신흥주가 목표)
    lam = 0.0 if pick_type == "longtail" else Combination.RISK_LAMBDA
    recs = []
    for i, (s, results, norm) in enumerate(zip(survivors, per_stock, norms)):
        comp = _composite(norm, weights)
        if lam > 0 and i in vol_pct_map:
            low_vol_score = 100.0 - vol_pct_map[i]
            final = (1 - lam) * comp + lam * low_vol_score
        else:
            final = comp
        recs.append(_build_recommendation(s, results, norm, final, weights, pick_type))

    # 6) 선정
    return _select_with_diversity(recs, top_n, max_per_primary)


def recommend(stocks: list[Stock],
              top_n: int = TOP_N,
              max_per_primary: int | None = MAX_PER_PRIMARY,
              weights: dict | None = None,
              apply_exclusion: bool = True,
              pick_type: str = "core") -> dict[str, list[Recommendation]]:
    """유니버스를 평가해 시장(KR/US)별 추천 리스트를 반환.

    weights: 부분 가중치 오버라이드(롱테일 등). apply_exclusion=False면 배제필터 생략.
    pick_type: 결과에 태깅("core"|"longtail").
    """
    by_market: dict[str, list[Stock]] = {}
    for s in stocks:
        by_market.setdefault(s.market, []).append(s)
    return {
        market: _recommend_market(mstocks, top_n, max_per_primary,
                                  weights, apply_exclusion, pick_type)
        for market, mstocks in by_market.items()
    }
