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

from .config import ApiKeys, TOP_N
from .datasources import KoreaDataSource, USDataSource, MockDataSource
from .engine import recommend


def collect_stocks():
    """키 유무에 따라 실제 소스/Mock 소스에서 종목을 모음."""
    use_real = any([ApiKeys.KIS_APP_KEY, ApiKeys.ALPHA_VANTAGE, ApiKeys.TWELVE_DATA])
    if use_real:
        kr = KoreaDataSource(ApiKeys.KIS_APP_KEY, ApiKeys.KIS_APP_SECRET, ApiKeys.DART_API_KEY)
        us = USDataSource(ApiKeys.ALPHA_VANTAGE, ApiKeys.TWELVE_DATA, ApiKeys.FINNHUB)
    else:
        kr = MockDataSource("KR")
        us = MockDataSource("US")
    return kr.fetch_universe() + us.fetch_universe(), use_real


def build_payload(result: dict) -> dict:
    """앱 소비용 최종 JSON 페이로드."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
        "markets": {
            market: [rec.to_dict() for rec in recs]
            for market, recs in result.items()
        },
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
    stocks, use_real = collect_stocks()
    result = recommend(stocks)
    payload = build_payload(result)

    # 출력 경로: 환경변수 OUTPUT_PATH > 기본값(저장소 루트 = 패키지 부모 디렉터리)
    out_path = os.environ.get("OUTPUT_PATH")
    if not out_path:
        out_path = str(Path(__file__).resolve().parent.parent / "recommendations.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    mode = "실제 API" if use_real else "Mock 데이터"
    print(f"[{mode}] 모드로 추천 생성 완료 → {out_path}")
    print_summary(payload)


if __name__ == "__main__":
    main()
