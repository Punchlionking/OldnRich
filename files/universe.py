"""
유니버스 동적 로더 — 지수 구성종목을 외부 소스에서 가져온다(하드코딩 X).

  · US: S&P500 구성종목 CSV(datahub) + 보충 → ~600 (themes=[GICS 섹터])
  · KR: 네이버 시총순위(코스피) 상위 N (우선주 제외)

유니버스는 분기 리밸런싱마다만 바뀌므로 캐시(기본 30일) + 실패 시 시드 폴백.
"""

from __future__ import annotations

import re
import logging
import urllib.request

log = logging.getLogger("stock_recommender.universe")

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_SP500_CSV = ("https://raw.githubusercontent.com/datasets/"
              "s-and-p-500-companies/main/data/constituents.csv")

# S&P500 외 보충용 유동성 높은 미장 종목(대형 ADR·인기주 등)
_US_SUPPLEMENT = [
    ("TSM", "TSMC", "Information Technology"), ("ASML", "ASML", "Information Technology"),
    ("BABA", "Alibaba", "Consumer Discretionary"), ("TM", "Toyota", "Consumer Discretionary"),
    ("SHOP", "Shopify", "Information Technology"), ("SE", "Sea Ltd", "Communication Services"),
    ("MELI", "MercadoLibre", "Consumer Discretionary"), ("SNOW", "Snowflake", "Information Technology"),
    ("COIN", "Coinbase", "Financials"), ("HOOD", "Robinhood", "Financials"),
    ("DDOG", "Datadog", "Information Technology"), ("NET", "Cloudflare", "Information Technology"),
    ("CRWD", "CrowdStrike", "Information Technology"), ("ZS", "Zscaler", "Information Technology"),
    ("PANW", "Palo Alto", "Information Technology"), ("MDB", "MongoDB", "Information Technology"),
    ("ABNB", "Airbnb", "Consumer Discretionary"), ("UBER", "Uber", "Industrials"),
    ("DASH", "DoorDash", "Consumer Discretionary"), ("RBLX", "Roblox", "Communication Services"),
    ("PLTR", "Palantir", "Information Technology"), ("U", "Unity", "Information Technology"),
    ("SQ", "Block", "Financials"), ("PYPL", "PayPal", "Financials"),
    ("ARM", "Arm Holdings", "Information Technology"), ("SMCI", "Super Micro", "Information Technology"),
    ("MRVL", "Marvell", "Information Technology"), ("ON", "ON Semi", "Information Technology"),
    ("CELH", "Celsius", "Consumer Staples"), ("DKNG", "DraftKings", "Consumer Discretionary"),
    ("RIVN", "Rivian", "Consumer Discretionary"), ("LCID", "Lucid", "Consumer Discretionary"),
    ("AFRM", "Affirm", "Financials"), ("UPST", "Upstart", "Financials"),
    ("ROKU", "Roku", "Communication Services"), ("PINS", "Pinterest", "Communication Services"),
    ("SNAP", "Snap", "Communication Services"), ("SPOT", "Spotify", "Communication Services"),
    ("TTD", "Trade Desk", "Communication Services"), ("TWLO", "Twilio", "Information Technology"),
    ("DOCU", "DocuSign", "Information Technology"), ("OKTA", "Okta", "Information Technology"),
    ("CVNA", "Carvana", "Consumer Discretionary"), ("W", "Wayfair", "Consumer Discretionary"),
    ("ENPH", "Enphase", "Information Technology"), ("FSLR", "First Solar", "Information Technology"),
    ("PLUG", "Plug Power", "Industrials"), ("CHPT", "ChargePoint", "Industrials"),
    ("NIO", "NIO", "Consumer Discretionary"), ("XPEV", "XPeng", "Consumer Discretionary"),
    ("LI", "Li Auto", "Consumer Discretionary"), ("GRAB", "Grab", "Industrials"),
    ("PDD", "PDD Holdings", "Consumer Discretionary"), ("JD", "JD.com", "Consumer Discretionary"),
    ("BIDU", "Baidu", "Communication Services"), ("NTES", "NetEase", "Communication Services"),
]


def _get(url: str, enc: str = "utf-8", timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(enc, "replace")


def load_us_universe(n: int = 600, cache=None) -> list[tuple[str, str, list[str]]]:
    """S&P500 + 보충 → (ticker, name, [sector])."""
    if cache is not None and cache.is_fresh("universe", "us", 30):
        cached = cache.get("universe", "us")
        if cached:
            return [(t, nm, th) for t, nm, th in cached][:n]
    out: list[tuple[str, str, list[str]]] = []
    seen: set[str] = set()
    try:
        csv = _get(_SP500_CSV)
        for line in csv.strip().splitlines()[1:]:
            parts = line.split(",")
            if len(parts) < 3:
                continue
            sym = parts[0].strip().replace(".", "-")   # BRK.B → BRK-B (Yahoo 형식)
            name = parts[1].strip().strip('"')
            sector = parts[2].strip().strip('"') or "기타"
            if sym and sym not in seen:
                seen.add(sym)
                out.append((sym, name, [sector]))
    except Exception as e:
        log.warning("[US] S&P500 로드 실패: %s", e)
    for sym, name, sector in _US_SUPPLEMENT:
        if sym not in seen:
            seen.add(sym)
            out.append((sym, name, [sector]))
    if not out:
        return list(_US_SEED)
    if cache is not None:
        cache.put("universe", "us", out)
    return out[:n]


def load_kr_universe(n: int = 200, cache=None) -> list[tuple[str, str, list[str]]]:
    """네이버 코스피 시총순위 상위 n (우선주 제외). themes는 KIS 업종으로 채움(빈 리스트)."""
    if cache is not None and cache.is_fresh("universe", "kr", 30):
        cached = cache.get("universe", "kr")
        if cached:
            return [(t, nm, th) for t, nm, th in cached][:n]
    out: list[tuple[str, str, list[str]]] = []
    seen: set[str] = set()
    pages = (n // 50) + 2
    for page in range(1, pages + 1):
        try:
            html = _get(f"https://finance.naver.com/sise/sise_market_sum.naver"
                        f"?sosok=0&page={page}", enc="euc-kr")
            for code, name in re.findall(r'code=(\d{6})"[^>]*>([^<]+)</a>', html):
                name = name.strip()
                if not name or code in seen:
                    continue
                # 우선주 제외(이름이 '우','우B','1우' 등으로 끝남)
                if re.search(r'우[A-Z]?$', name) or name.endswith("우B"):
                    continue
                seen.add(code)
                out.append((code, name, []))    # themes는 수집 시 KIS 업종으로
                if len(out) >= n:
                    break
        except Exception as e:
            log.warning("[KR] 네이버 시총 p%d 실패: %s", page, e)
        if len(out) >= n:
            break
    if not out:
        return list(_KR_SEED)
    if cache is not None:
        cache.put("universe", "kr", out)
    return out[:n]


# 폴백 시드(외부 소스 전부 실패 시)
_KR_SEED = [
    ("005930", "삼성전자", []), ("000660", "SK하이닉스", []), ("373220", "LG에너지솔루션", []),
    ("207940", "삼성바이오로직스", []), ("005380", "현대차", []), ("000270", "기아", []),
]
_US_SEED = [
    ("NVDA", "NVIDIA", ["Information Technology"]), ("AAPL", "Apple", ["Information Technology"]),
    ("MSFT", "Microsoft", ["Information Technology"]), ("AMZN", "Amazon", ["Consumer Discretionary"]),
    ("GOOGL", "Alphabet", ["Communication Services"]), ("META", "Meta", ["Communication Services"]),
]
