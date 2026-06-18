"""
진입점.

실행:  python -m stock_recommender.main
결과:  recommendations.json 생성 (안드로이드 앱이 그대로 받아쓰는 형식)
       + 콘솔에 요약 출력

API 키가 환경변수에 설정돼 있으면 실제 소스, 없으면 Mock 데이터로 동작합니다.
"""

from __future__ import annotations

import json
import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

# Windows 콘솔 UTF-8 강제 설정 (이모지 출력용)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
    stream=sys.stderr,
)


def _load_env():
    """같은 디렉터리의 .env 파일을 읽어 환경변수에 주입 (python-dotenv 없이도 동작)."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key and key not in os.environ:   # 이미 설정된 환경변수는 덮어쓰지 않음
                os.environ[key] = val

_load_env()   # config.py 보다 먼저 호출해야 ApiKeys가 키를 인식함

from .config import (ApiKeys, TOP_N, LONGTAIL_N, LONGTAIL_WEIGHTS, CacheTTL,
                     UNIVERSE_KR_N, UNIVERSE_US_N)
from .datasources import (KoreaDataSource, USDataSource, MockDataSource,
                          _KR_LONGTAIL, _US_LONGTAIL)
from .engine import recommend
from .cache import CacheStore
from .universe import load_kr_universe, load_us_universe


def _dedup_universe(rows):
    seen, out = set(), []
    for t, nm, th in rows:
        if t not in seen:
            seen.add(t)
            out.append((t, nm, th))
    return out


def _make_sources():
    """(sources, cache) 반환. cache는 계층적 캐시(없으면 None)."""
    use_real = any([ApiKeys.KIS_APP_KEY, ApiKeys.ALPHA_VANTAGE, ApiKeys.TWELVE_DATA])
    if not use_real:
        return {"KR": MockDataSource("KR"), "US": MockDataSource("US")}, None

    cache = CacheStore()
    # 카테고리별 '1회 실행당 새 호출 예산' (오래된 것부터 순환 갱신)
    for cat, n in (("kr_fin", CacheTTL.BUDGET_KR_FUND),
                   ("kr_dartfin", CacheTTL.BUDGET_KR_FUND),
                   ("kr_gov", CacheTTL.BUDGET_KR_GOV),
                   ("kr_ins", CacheTTL.BUDGET_KR_INSIDER),
                   ("kr_analyst", CacheTTL.BUDGET_KR_ANALYST),
                   ("us_av", CacheTTL.BUDGET_US_FUND_AV),
                   ("us_metric", CacheTTL.BUDGET_US_METRIC),   # Finnhub ROE/PER (60/분)
                   ("us_news", CacheTTL.BUDGET_US_FIN_FH),
                   ("us_fin", CacheTTL.BUDGET_US_FIN_FH),
                   ("us_analyst", CacheTTL.BUDGET_US_ANALYST),
                   ("us_ins", CacheTTL.BUDGET_US_INSIDER)):
        cache.set_budget(cat, n)

    # 코어 유니버스(동적) + 롱테일(큐레이션) 결합 후 중복 제거
    kr_uni = _dedup_universe(load_kr_universe(UNIVERSE_KR_N, cache) + _KR_LONGTAIL)
    us_uni = _dedup_universe(load_us_universe(UNIVERSE_US_N, cache) + _US_LONGTAIL)
    print(f"[유니버스] KR {len(kr_uni)} (코어+롱테일) / US {len(us_uni)}")
    return {
        "KR": KoreaDataSource(ApiKeys.KIS_APP_KEY, ApiKeys.KIS_APP_SECRET,
                              ApiKeys.DART_API_KEY, universe=kr_uni, cache=cache),
        "US": USDataSource(ApiKeys.ALPHA_VANTAGE, ApiKeys.TWELVE_DATA,
                           ApiKeys.FINNHUB, universe=us_uni, cache=cache),
    }, cache


def _load_previous(out_path: str) -> dict | None:
    try:
        with open(out_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def build_payload(out_path: str) -> dict:
    """
    시장별로 독립 수집. 한 시장이 실패하면(예: CI에서 KIS 불가) 그 시장은
    '이전 실데이터'를 유지하고, 성공한 시장만 갱신한다. 가짜(Mock) 발행 방지.
    """
    sources, cache = _make_sources()
    prev = _load_previous(out_path) or {}
    prev_markets = (prev.get("markets") or {})
    prev_meta = (prev.get("market_meta") or {})

    now_iso = datetime.now(timezone.utc).isoformat()
    markets: dict = {}
    meta: dict = {}

    # ENABLE_MARKETS=KR (로컬·한국) / US (CI·미국) 처럼 시장 분담 가능. 기본 전체.
    enabled = {m.strip().upper()
               for m in os.environ.get("ENABLE_MARKETS", "KR,US").split(",") if m.strip()}

    for market in ("KR", "US"):
        # 비활성 시장: 이전 데이터를 그대로 보존(다른 러너가 담당) — stale 아님
        if market not in enabled:
            markets[market] = prev_markets.get(market, [])
            meta[market] = prev_meta.get(market, {"source": "preserved", "as_of": "unknown"})
            print(f"[{market}] 비활성(ENABLE_MARKETS) → 이전 데이터 보존")
            continue
        src = sources[market]
        try:
            stocks = src.fetch_universe()
            # 코어: TOP 5 (우량/종합) — 전체 유니버스 대상
            core = recommend(stocks, top_n=TOP_N).get(market, [])
            # 롱테일: 전체 유니버스에서 코어 선정 종목만 제외하고 공격적 가중치로 재탐색
            core_tickers = {r.ticker for r in core}
            long_stocks = [s for s in stocks if s.ticker not in core_tickers]
            long = recommend(long_stocks, top_n=LONGTAIL_N, max_per_primary=None,
                             weights=LONGTAIL_WEIGHTS, apply_exclusion=False,
                             pick_type="longtail").get(market, [])
            recs = core + long
            markets[market] = [rec.to_dict() for rec in recs]
            mode = getattr(src, "data_mode", "real")
            meta[market] = {"source": mode, "as_of": now_iso}
            print(f"[{market}] {mode} 데이터로 코어 {len(core)} + 롱테일 {len(long)}종목 생성")
        except Exception as e:
            # 실패 → 이전 실데이터 유지(있으면), 없으면 빈 리스트
            print(f"[{market}] 수집 실패: {e}")
            print(f"[{market}] → 이전 데이터 유지(가짜 발행 방지)")
            markets[market] = prev_markets.get(market, [])
            kept = prev_meta.get(market, {})
            meta[market] = {
                "source": kept.get("source", "stale"),
                "as_of": kept.get("as_of", "unknown"),
                "stale": True,
            }

    # 캐시 저장(이번에 새로 받은 느린 데이터 영속화 → 다음 실행에서 재사용)
    if cache is not None:
        cache.save()
        print(f"[캐시] 이번 실행 새 호출 {cache.fetched}건 (나머지는 캐시 재사용)")

    return {
        "generated_at": now_iso,
        "version": 2,
        "markets": markets,
        "market_meta": meta,   # 시장별 출처/시점/staleness
    }


def print_summary(payload: dict):
    for market, label in (("KR", "🇰🇷 국장"), ("US", "🇺🇸 미장")):
        print(f"\n===== {label} 오늘의 추천 TOP {TOP_N} =====")
        for i, rec in enumerate(payload["markets"].get(market, []), 1):
            risk = " ⚠️고위험" if rec["risk_level"] == "높음" else ""
            print(f"{i}. [{rec['target_horizon']}] {rec['name']} ({rec['ticker']})  "
                  f"점수 {rec['overall_score']}  · 대표기준: {rec['primary_label']}{risk}")
            print(f"     └ {rec['reasons'][0]['reason']}")


def main():
    # 출력 경로: 환경변수 OUTPUT_PATH > 기본값(저장소 루트 = 패키지 부모 디렉터리)
    out_path = os.environ.get("OUTPUT_PATH")
    if not out_path:
        out_path = str(Path(__file__).resolve().parent.parent / "recommendations.json")

    payload = build_payload(out_path)   # 이전본 참조 위해 경로 전달

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"추천 생성 완료 → {out_path}")
    for m, meta in payload.get("market_meta", {}).items():
        tag = f"{meta.get('source')}" + (" ⚠️STALE(이전데이터 유지)" if meta.get("stale") else "")
        print(f"  {m}: {tag}")
    print_summary(payload)


if __name__ == "__main__":
    main()
