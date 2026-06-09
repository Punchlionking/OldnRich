"""
데이터 소스 계층.

- DataSource: 추상 인터페이스. "유니버스를 받아 Stock 리스트를 만든다".
- MockDataSource: API 키 없이도 엔진 전체가 돌아가도록 현실적인 더미 데이터 생성.
- KoreaDataSource / USDataSource: 실제 API 연동 '골격'. 각 메서드 주석에
  어떤 API의 어떤 엔드포인트로 무엇을 채워야 하는지 적어두었습니다.
  (실제 호출 코드는 API 키와 계정이 필요하므로 TODO로 비워둠 → Mock으로 폴백)

==== 실제 연동 시 채워야 할 데이터 ↔ API 매핑 ====

[국장 / KR]
  시세·거래량·기술지표  → 한국투자증권 KIS Developers
      · 현재가:        /uapi/domestic-stock/v1/quotations/inquire-price
      · 기간별 시세:   .../inquire-daily-itemchartprice (RSI/MACD/MA 계산용)
      · 순위/거래량급증: [국내주식] 순위분석 API
  재무·공시(PER/PBR/ROE/실적) → DART 오픈API + KIS [종목정보]
  업종 평균 PER/PBR    → KIS [업종/기타] 또는 별도 집계
  목표가(컨센서스)     → 네이버 금융 / FnGuide 스크래핑 (약관 확인 필수)
  테마 분류            → 사전 구축한 테마-종목 매핑 테이블
  뉴스/감성            → 네이버 뉴스 등 (한국어 감성분석 별도 필요)

[미장 / US]
  시세·기술지표        → Twelve Data (기술지표 130+ 내장) 또는 Alpha Vantage
  펀더멘털(PER/ROE/마진) → Alpha Vantage Fundamentals 또는 Financial Modeling Prep
  실적 분기 시계열     → FMP / Alpha Vantage income statement
  목표가·애널리스트수  → Finnhub (analyst price target / recommendation)
  뉴스/감성            → Finnhub news + sentiment
  테마/섹터 강도       → 섹터 ETF 상대강도 등으로 산출
"""

from __future__ import annotations

import random
import time
import logging
import datetime as dt
from abc import ABC, abstractmethod
from collections import defaultdict

from .models import (
    Stock, FinancialData, TechData, SentimentData,
    AnalystData, ThemeData, BeneficiaryData, BlogData,
    QualityData, AnalystExtData, GovernanceData, InsiderData, RedFlagData,
)
from . import indicators as ind

log = logging.getLogger("stock_recommender.datasources")


def _f(value, default: float = 0.0) -> float:
    """문자열/None 섞인 API 응답을 안전하게 float로 변환."""
    try:
        if value in (None, "", "None", "-"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class DataSource(ABC):
    @abstractmethod
    def fetch_universe(self) -> list[Stock]:
        """평가 대상 종목 전체를 Stock 리스트로 반환."""
        ...


# ---------------------------------------------------------------------------
# Mock 데이터 소스 (시드 고정으로 재현 가능)
# ---------------------------------------------------------------------------
_KR_UNIVERSE = [
    ("005930", "삼성전자", ["반도체", "AI"]),
    ("000660", "SK하이닉스", ["반도체", "HBM"]),
    ("373220", "LG에너지솔루션", ["2차전지"]),
    ("207940", "삼성바이오로직스", ["바이오", "CDMO"]),
    ("005380", "현대차", ["자동차", "전기차"]),
    ("035420", "NAVER", ["AI", "플랫폼"]),
    ("000270", "기아", ["자동차"]),
    ("068270", "셀트리온", ["바이오"]),
    ("105560", "KB금융", ["금융", "밸류업"]),
    ("012450", "한화에어로스페이스", ["방산"]),
    ("042700", "한미반도체", ["반도체", "HBM"]),
    ("247540", "에코프로비엠", ["2차전지", "양극재"]),
]

_US_UNIVERSE = [
    ("NVDA", "NVIDIA", ["AI", "Semiconductor"]),
    ("AAPL", "Apple", ["Bigtech"]),
    ("MSFT", "Microsoft", ["AI", "Cloud"]),
    ("AMZN", "Amazon", ["Cloud", "Retail"]),
    ("GOOGL", "Alphabet", ["AI", "Adtech"]),
    ("META", "Meta", ["AI", "Adtech"]),
    ("TSLA", "Tesla", ["EV", "Robotics"]),
    ("AMD", "AMD", ["AI", "Semiconductor"]),
    ("PLTR", "Palantir", ["AI", "Defense"]),
    ("AVGO", "Broadcom", ["AI", "Semiconductor"]),
    ("MU", "Micron", ["Semiconductor", "HBM"]),
    ("UNH", "UnitedHealth", ["Healthcare"]),
]


class MockDataSource(DataSource):
    def __init__(self, market: str, seed: int = 42):
        self.market = market
        self.rng = random.Random(seed + (0 if market == "KR" else 1000))

    def fetch_universe(self) -> list[Stock]:
        universe = _KR_UNIVERSE if self.market == "KR" else _US_UNIVERSE
        currency = "KRW" if self.market == "KR" else "USD"
        return [self._make_stock(t, n, themes, currency) for t, n, themes in universe]

    def _make_stock(self, ticker, name, themes, currency) -> Stock:
        r = self.rng
        price = r.uniform(40000, 120000) if currency == "KRW" else r.uniform(40, 600)
        sector_per = r.uniform(12, 25)
        sector_pbr = r.uniform(1.5, 4.0)

        # 실적 분기 시계열: 성장형/정체형을 섞어서 다양하게
        base = r.uniform(800, 5000)
        growth = r.uniform(0.95, 1.15)
        rev = [base * (growth ** i) for i in range(6)]
        rev.reverse()                          # [0]이 최신이 되도록
        op = [v * r.uniform(0.08, 0.25) for v in rev]

        # 일봉 종가 시계열(약 260거래일) 생성 — 모멘텀/변동성/리드-래그용
        drift = r.uniform(-0.0008, 0.0018)     # 종목별 추세
        vol_daily = r.uniform(0.012, 0.035)    # 종목별 변동성
        closes = self._synth_closes(price, 260, drift, vol_daily)
        mom = ind.momentum_12_1(closes)
        volat = ind.annualized_volatility(closes)

        # 재무제표 기반 품질팩터 입력(Mock) — 실데이터 연동 전 데모용
        total_assets = base * r.uniform(8, 20)
        net_income = op[0] * r.uniform(0.6, 0.9)
        cfo = net_income * r.uniform(0.7, 1.4)
        quality = QualityData(
            roa=net_income / total_assets * 100, roa_prev=r.uniform(2, 12),
            cfo=cfo, net_income=net_income,
            leverage=r.uniform(0.1, 0.5), leverage_prev=r.uniform(0.1, 0.5),
            current_ratio=r.uniform(0.9, 2.5), current_ratio_prev=r.uniform(0.9, 2.5),
            shares_out=1e8, shares_out_prev=1e8 * r.uniform(0.98, 1.03),
            gross_margin=r.uniform(15, 45), gross_margin_prev=r.uniform(15, 45),
            asset_turnover=r.uniform(0.4, 1.2), asset_turnover_prev=r.uniform(0.4, 1.2),
            fcf=cfo - base * r.uniform(0.05, 0.2),
            market_cap=total_assets * r.uniform(0.8, 3.0),  # 재무제표와 단위 정합
            nopat=op[0] * 0.78, invested_capital=total_assets * r.uniform(0.5, 0.8),
            wacc=r.uniform(6, 11),
            working_capital=total_assets * r.uniform(0.05, 0.3),
            retained_earnings=total_assets * r.uniform(0.1, 0.5),
            ebit=op[0], total_assets=total_assets,
            total_liabilities=total_assets * r.uniform(0.2, 0.7),
            sales=rev[0],
        )

        leader_pool = [u[0] for u in (_KR_UNIVERSE if self.market == "KR" else _US_UNIVERSE)
                       if u[0] != ticker]
        has_leader = r.random() > 0.4
        return Stock(
            ticker=ticker, name=name, market=self.market, currency=currency,
            financial=FinancialData(
                per=r.uniform(6, 30),
                pbr=r.uniform(0.6, 5.0),
                sector_per=sector_per,
                sector_pbr=sector_pbr,
                roe=r.uniform(3, 28),
                operating_margin=r.uniform(2, 35),
                debt_ratio=r.uniform(20, 220),
                revenue_quarters=rev,
                op_income_quarters=op,
            ),
            tech=TechData(
                current_price=closes[-1],
                volume=r.uniform(1e6, 2e7),
                avg_volume_20d=r.uniform(1e6, 1e7),
                price_change_5d=ind.pct_change(closes, 5),
                rsi_14=ind.rsi(closes),
                macd=r.uniform(-2, 2),
                macd_signal=r.uniform(-2, 2),
                macd_prev_diff=r.uniform(-1.5, 1.5),
                bb_position=ind.bollinger_position(closes),
                ma20=price * r.uniform(0.95, 1.05),
                ma60=price * r.uniform(0.9, 1.1),
                mom_12_1=mom, volatility=volat, closes=closes,
            ),
            sentiment=SentimentData(
                news_count_today=r.randint(0, 30),
                avg_news_count=r.uniform(3, 12),
                sentiment_score=r.uniform(-0.5, 0.9),
                sentiment_prev=r.uniform(-0.5, 0.6),
            ),
            analyst=AnalystData(
                target_mean=price * r.uniform(0.9, 1.6),
                num_analysts=r.randint(0, 20),
            ),
            theme=ThemeData(
                themes=themes,
                theme_volume_surge=r.uniform(0.8, 3.5),
                sector_strength_pct=r.uniform(20, 99),
            ),
            beneficiary=BeneficiaryData(
                leader_ticker=r.choice(leader_pool) if has_leader else None,
                leader_change_5d=r.uniform(5, 35),
                own_change_5d=r.uniform(-3, 12),
                correlation=r.uniform(0.3, 0.9),
                lead_lag_days=r.randint(1, 4) if has_leader and r.random() > 0.4 else 0,
                lead_lag_corr=r.uniform(0.3, 0.7) if has_leader else 0.0,
            ),
            blog=BlogData(
                mention_count_7d=r.randint(0, 9),
                source_count=r.randint(0, 4),
                days_since_last=r.uniform(0, 8),
            ),
            quality=quality,
            analyst_ext=AnalystExtData(
                estimate_revision_pct=r.uniform(-5, 10),
                earnings_surprise_pct=r.uniform(-3, 12),
                days_since_earnings=r.uniform(1, 60),
            ),
            governance=GovernanceData(
                total_payout_ratio=r.uniform(0, 12) if self.market == "KR" else r.uniform(0, 8),
                buyback_cancel=r.random() > 0.7,
                valueup_enrolled=r.random() > 0.6 if self.market == "KR" else None,
                governance_score=r.uniform(30, 90),
            ) if self.market == "KR" or r.random() > 0.5 else GovernanceData(),
            insider=InsiderData(
                net_insider_buy_90d=r.uniform(-1e9, 3e9),
                buyer_count_90d=r.randint(0, 4),
            ),
        )

    @staticmethod
    def _synth_closes(last_price: float, n: int, drift: float, vol: float) -> list[float]:
        """기하 브라운 운동 비슷한 합성 종가 시계열(과거→최신). 마지막이 현재가 근처."""
        import random as _rnd
        rng = _rnd.Random(hash((round(last_price, 2), n)) & 0xFFFFFFFF)
        # 현재가에서 거꾸로 생성 후 뒤집기
        prices = [last_price]
        for _ in range(n - 1):
            step = drift + vol * rng.gauss(0, 1)
            prices.append(prices[-1] / (1.0 + step))
        prices.reverse()
        return [max(1.0, p) for p in prices]


# ---------------------------------------------------------------------------
# 실제 API 소스 골격 (키 없으면 Mock으로 폴백)
# ---------------------------------------------------------------------------
class KoreaDataSource(DataSource):
    """
    한국투자증권 KIS Open API 연동.

    가져오는 데이터:
      · inquire-price (FHKST01010100)            → 현재가, PER, PBR, 거래량, 업종명
      · inquire-daily-itemchartprice (FHKST03010100) → 일봉 → RSI/MACD/볼린저 직접계산
      · finance/financial-ratio (FHKST66430300)  → ROE
      · finance/income-statement (FHKST66430200) → 분기 매출/영업이익(실적 시계열)
      · 업종 평균 PER/PBR → 유니버스 내 같은 업종 종목들의 평균으로 산출

    제공 안 되는 데이터(중립값으로 채우고 별도 소스 필요):
      · 목표가(컨센서스)  → 네이버 금융/FnGuide 스크래핑 (약관 확인)
      · 뉴스/감성        → 네이버 뉴스 + 한국어 감성분석
      · 테마 급증/수혜/블로그 → 사전 매핑 테이블 / 별도 집계
    즉 키만 넣으면 #1·#4·#7(저평가·퀀트·실적)은 실데이터로, 나머지는
    중립 점수로 동작하며, 위 소스를 추가할수록 정밀해집니다.
    """

    # 실전: openapi.koreainvestment.com:9443
    # 모의: openapivts.koreainvestment.com:29443
    REAL_BASE    = "https://openapi.koreainvestment.com:9443"
    VIRTUAL_BASE = "https://openapivts.koreainvestment.com:29443"

    def __init__(self, kis_key, kis_secret, dart_key=None,
                 universe=None, rate_limit_sec: float = 1.1,
                 virtual: bool | None = None):
                 # FHKST03010100(일봉) 등 일부 TR은 초당 1건 제한 → 1.1초 간격
        self.kis_key = kis_key
        self.kis_secret = kis_secret
        self.dart_key = dart_key
        self.universe = universe or _KR_UNIVERSE
        self.rate_limit_sec = rate_limit_sec   # KIS는 초당 호출 제한 → 간격 둠

        # virtual=None 이면 키 길이로 자동 판단
        # 실전 앱키는 보통 36자(UUID), 모의는 형식이 다양함.
        # 명시적으로 env KIS_VIRTUAL=1 로 제어 가능.
        import os as _os
        if virtual is None:
            virtual = _os.environ.get("KIS_VIRTUAL", "0").strip() == "1"
        self.BASE = self.VIRTUAL_BASE if virtual else self.REAL_BASE
        self._is_virtual = virtual
        log.info("[KR] KIS 모드: %s  BASE=%s", "모의" if virtual else "실전", self.BASE)

        self._token = None
        self._token_exp = 0.0
        self._last_call = 0.0

    # --- 저수준 HTTP 헬퍼 ---------------------------------------------------
    @staticmethod
    def _requests():
        import requests          # 지연 import → Mock 모드에선 불필요
        return requests

    def _throttle(self):
        wait = self.rate_limit_sec - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        r = self._requests().post(
            f"{self.BASE}/oauth2/tokenP",
            json={"grant_type": "client_credentials",
                  "appkey": self.kis_key, "appsecret": self.kis_secret},
            headers={"Content-Type": "application/json"}, timeout=10,
        )
        if not r.ok:
            log.error("[KR] 토큰 발급 실패 status=%s body=%s", r.status_code, r.text[:300])
            r.raise_for_status()
        d = r.json()
        if "access_token" not in d:
            raise RuntimeError(f"[KR] 토큰 응답에 access_token 없음: {d}")
        self._token = d["access_token"]
        self._token_exp = time.time() + int(d.get("expires_in", 86400))
        log.info("[KR] 토큰 발급 성공 (만료까지 %.0f초)", self._token_exp - time.time())
        return self._token

    def _get(self, path: str, tr_id: str, params: dict,
             _retry: int = 3, _retry_wait: float = 2.0) -> dict:
        """KIS GET 요청. EGW00201(초당 한도초과) 발생 시 _retry 횟수만큼 재시도."""
        self._throttle()
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self._get_token()}",
            "appkey": self.kis_key,
            "appsecret": self.kis_secret,
            "tr_id": tr_id,
            "custtype": "P",      # P=개인
        }
        r = self._requests().get(f"{self.BASE}{path}", headers=headers,
                                 params=params, timeout=10)
        if not r.ok:
            body_text = r.text[:300]
            # EGW00201 = 초당 한도초과 → 재시도
            if r.status_code == 500 and "EGW00201" in body_text and _retry > 0:
                log.warning("[KR] 초당 한도초과(EGW00201) tr_id=%s → %.1fs 후 재시도(%d회 남음)",
                            tr_id, _retry_wait, _retry - 1)
                time.sleep(_retry_wait)
                self._last_call = 0.0   # 강제 대기 초기화
                return self._get(path, tr_id, params,
                                 _retry=_retry - 1, _retry_wait=_retry_wait * 1.5)
            log.error("[KR] API 오류 tr_id=%s status=%s body=%s",
                      tr_id, r.status_code, body_text)
            r.raise_for_status()
        body = r.json()
        # KIS는 HTTP 200이어도 rt_cd != "0" 이면 오류
        rt = body.get("rt_cd")
        if rt not in (None, "0", 0):
            msg_cd = body.get("msg_cd", "")
            msg = body.get("msg1") or body.get("msg") or str(body)
            # 초당 한도초과가 200으로 오는 경우 대비
            if msg_cd == "EGW00201" and _retry > 0:
                log.warning("[KR] 초당 한도초과(200) tr_id=%s → %.1fs 재시도",
                            tr_id, _retry_wait)
                time.sleep(_retry_wait)
                self._last_call = 0.0
                return self._get(path, tr_id, params,
                                 _retry=_retry - 1, _retry_wait=_retry_wait * 1.5)
            raise RuntimeError(f"[KR] KIS 오류 rt_cd={rt} {msg_cd} {msg}")
        return body

    # --- 개별 엔드포인트 ----------------------------------------------------
    def _quote(self, ticker: str) -> dict:
        d = self._get("/uapi/domestic-stock/v1/quotations/inquire-price",
                      "FHKST01010100",
                      {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker})
        o = d.get("output", {}) or {}
        return {
            "price": _f(o.get("stck_prpr")),
            "per": _f(o.get("per")),
            "pbr": _f(o.get("pbr")),
            "volume": _f(o.get("acml_vol")),
            "sector": o.get("bstp_kor_isnm", ""),
        }

    def _daily(self, ticker: str, days: int = 400) -> tuple[list[float], list[float]]:
        # 모멘텀(12-1)에 ~252거래일 필요 → 달력일 400일(≈280거래일) 조회
        end = dt.date.today()
        start = end - dt.timedelta(days=days)
        d = self._get("/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
                      "FHKST03010100",
                      {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker,
                       "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
                       "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
                       "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"})
        rows = d.get("output2", []) or []
        closes, vols = [], []
        for row in reversed(rows):                  # 응답은 최신→과거. 과거→최신으로 뒤집음
            c = _f(row.get("stck_clpr"))
            if c > 0:
                closes.append(c)
                vols.append(_f(row.get("acml_vol")))
        return closes, vols

    def _financials(self, ticker: str) -> tuple[float, float, list[float], list[float]]:
        """ROE(%), 영업이익률(%), 분기 매출[], 분기 영업이익[] (최신이 [0]).
        ※ 재무 엔드포인트 필드명은 KIS 포털 응답 샘플로 검증 권장."""
        roe = op_margin = 0.0
        rev: list[float] = []
        op: list[float] = []
        common = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": ticker}
        try:
            d = self._get("/uapi/domestic-stock/v1/finance/financial-ratio",
                          "FHKST66430300", {**common, "FID_DIV_CLS_CODE": "0"})
            rows = d.get("output", []) or []
            if rows:
                roe = _f(rows[0].get("roe_val"))
        except Exception as e:
            log.warning("[KR] %s ROE 조회 실패: %s", ticker, e)
        try:
            d = self._get("/uapi/domestic-stock/v1/finance/income-statement",
                          "FHKST66430200", {**common, "FID_DIV_CLS_CODE": "1"})  # 1=분기
            rows = d.get("output", []) or []
            rev = [_f(r.get("sale_account")) for r in rows]     # 매출액
            op = [_f(r.get("bsop_prti")) for r in rows]         # 영업이익
            if rev and rev[0]:
                op_margin = (op[0] / rev[0]) * 100 if op else 0.0
        except Exception as e:
            log.warning("[KR] %s 손익 조회 실패: %s", ticker, e)
        return roe, op_margin, rev, op

    # --- 조립 ---------------------------------------------------------------
    def fetch_universe(self) -> list[Stock]:
        if not (self.kis_key and self.kis_secret):
            log.info("[KR] KIS 키 없음 → Mock 데이터 사용")
            return MockDataSource("KR").fetch_universe()

        raw = []
        for ticker, name, themes in self.universe:
            try:
                q = self._quote(ticker)
                closes, vols = self._daily(ticker)
                roe, opm, rev, op = self._financials(ticker)
                raw.append((ticker, name, themes, q, closes, vols, roe, opm, rev, op))
            except Exception as e:
                log.warning("[KR] %s 수집 실패: %s", ticker, e)

        if not raw:
            log.error("[KR] 실데이터 전체 실패 → Mock 폴백")
            return MockDataSource("KR").fetch_universe()

        # 업종 평균 PER/PBR
        per_by_sector, pbr_by_sector = defaultdict(list), defaultdict(list)
        for _, _, _, q, *_ in raw:
            if q["per"] > 0:
                per_by_sector[q["sector"]].append(q["per"])
            if q["pbr"] > 0:
                pbr_by_sector[q["sector"]].append(q["pbr"])

        def avg(xs):
            return sum(xs) / len(xs) if xs else 0.0

        stocks = []
        for ticker, name, themes, q, closes, vols, roe, opm, rev, op in raw:
            avg_vol20 = avg(vols[-20:]) if vols else q["volume"]
            macd_last, macd_sig, macd_prev = ind.macd(closes)
            stocks.append(Stock(
                ticker=ticker, name=name, market="KR", currency="KRW",
                financial=FinancialData(
                    per=q["per"], pbr=q["pbr"],
                    sector_per=avg(per_by_sector[q["sector"]]) or q["per"],
                    sector_pbr=avg(pbr_by_sector[q["sector"]]) or q["pbr"],
                    roe=roe, operating_margin=opm, debt_ratio=0.0,  # 부채비율: 안정성비율 API 추가 시
                    revenue_quarters=rev, op_income_quarters=op,
                ),
                tech=TechData(
                    current_price=q["price"] or (closes[-1] if closes else 0.0),
                    volume=q["volume"], avg_volume_20d=avg_vol20,
                    price_change_5d=ind.pct_change(closes, 5),
                    rsi_14=ind.rsi(closes),
                    macd=macd_last, macd_signal=macd_sig, macd_prev_diff=macd_prev,
                    bb_position=ind.bollinger_position(closes),
                    ma20=avg(closes[-20:]) if closes else 0.0,
                    ma60=avg(closes[-60:]) if closes else 0.0,
                    # LIVE: 일봉으로 중기 모멘텀·변동성 계산
                    mom_12_1=ind.momentum_12_1(closes),
                    volatility=ind.annualized_volatility(closes),
                    closes=closes,
                ),
                # 아래는 KIS 외 소스 필요 → 중립 기본값(엔진이 자동으로 제외 처리)
                sentiment=SentimentData(0, 1.0, 0.0, 0.0),
                analyst=AnalystData(target_mean=0.0, num_analysts=0),   # TODO: 네이버/FnGuide 목표가
                theme=ThemeData(themes=themes, theme_volume_surge=1.0, sector_strength_pct=50.0),
                beneficiary=BeneficiaryData(),
                blog=BlogData(),
                # TODO(데이터 연동): quality(DART 재무제표 → F-Score/FCF/ROIC/Altman/Accruals),
                #   analyst_ext(FnGuide 추정치), governance(DART 배당·자사주·밸류업),
                #   insider(DART 지분변동), red_flag(감사의견·감사인교체)
            ))
        log.info("[KR] %d/%d 종목 수집 완료", len(stocks), len(self.universe))
        return stocks


class USDataSource(DataSource):
    """
    미장 연동: Twelve Data(시세·지표) + Alpha Vantage(펀더멘털·목표가) + Finnhub(뉴스).

    가져오는 데이터:
      · Twelve Data /quote, /rsi, /macd, /bbands, /time_series → 시세·기술지표
      · Alpha Vantage OVERVIEW → PER, PBR, ROE, 영업이익률, 목표가, 섹터
      · Alpha Vantage INCOME_STATEMENT → 분기 매출/영업이익(실적 시계열)
      · Finnhub /company-news → 최근 뉴스 건수(감성은 별도 NLP 필요)

    ⚠ Alpha Vantage 무료 티어는 25 req/day로 매우 빡빡합니다(종목당 OVERVIEW+
      INCOME 2콜 → 12종목이면 하루 한도 소진). 운영 시 (a) 펀더멘털은 분기마다만
      바뀌므로 일/주 단위 캐시, (b) 유료 티어, (c) FMP로 대체를 권장합니다.
    """

    TD_BASE = "https://api.twelvedata.com"
    AV_BASE = "https://www.alphavantage.co/query"
    FH_BASE = "https://finnhub.io/api/v1"

    def __init__(self, alpha_key, twelve_key, finnhub_key=None,
                 universe=None, rate_limit_sec: float = 8.5):
                 # Twelve Data 무료 플랜: 8 req/min → 최소 7.5초 간격 필요
        self.alpha_key = alpha_key
        self.twelve_key = twelve_key
        self.finnhub_key = finnhub_key
        self.universe = universe or _US_UNIVERSE
        self.rate_limit_sec = rate_limit_sec
        self._last_call = 0.0

    @staticmethod
    def _requests():
        import requests
        return requests

    def _throttle(self):
        wait = self.rate_limit_sec - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

    def _get(self, url: str, params: dict) -> dict:
        self._throttle()
        r = self._requests().get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    # --- Twelve Data: 시세 & 기술지표 --------------------------------------
    def _td(self, path: str, ticker: str, extra: dict | None = None) -> dict:
        params = {"symbol": ticker, "apikey": self.twelve_key}
        if extra:
            params.update(extra)
        return self._get(f"{self.TD_BASE}/{path}", params)

    def _tech(self, ticker: str) -> dict:
        quote = self._td("quote", ticker)
        rsi_v = self._td("rsi", ticker, {"interval": "1day", "time_period": 14, "outputsize": 1})
        macd_v = self._td("macd", ticker, {"interval": "1day", "outputsize": 2})
        bb_v = self._td("bbands", ticker, {"interval": "1day", "time_period": 20, "outputsize": 1})
        # 모멘텀(12-1)·변동성 계산 위해 ~290거래일 조회 (콜 수 증가 없음, outputsize만 ↑)
        ts = self._td("time_series", ticker, {"interval": "1day", "outputsize": 290})

        price = _f(quote.get("close"))
        # RSI
        rsi_vals = rsi_v.get("values", [{}])
        rsi = _f(rsi_vals[0].get("rsi"), 50.0) if rsi_vals else 50.0
        # MACD (values[0]=최신, [1]=전일)
        mvals = macd_v.get("values", [])
        macd_last = _f(mvals[0].get("macd")) if mvals else 0.0
        macd_sig = _f(mvals[0].get("macd_signal")) if mvals else 0.0
        macd_prev = (_f(mvals[1].get("macd")) - _f(mvals[1].get("macd_signal"))) if len(mvals) > 1 else 0.0
        # 볼린저 위치
        bvals = bb_v.get("values", [{}])
        upper = _f(bvals[0].get("upper_band")) if bvals else 0.0
        lower = _f(bvals[0].get("lower_band")) if bvals else 0.0
        bb_pos = (price - lower) / (upper - lower) if upper > lower else 0.5
        bb_pos = max(0.0, min(1.0, bb_pos))
        # 5일 등락률 + 종가 시계열(과거→최신)
        tvals = ts.get("values", [])
        closes_newest_first = [_f(v.get("close")) for v in tvals]
        change_5d = 0.0
        if len(closes_newest_first) > 5 and closes_newest_first[5]:
            change_5d = (closes_newest_first[0] / closes_newest_first[5] - 1.0) * 100.0
        closes = [c for c in reversed(closes_newest_first) if c > 0]

        return {
            "price": price,
            "volume": _f(quote.get("volume")),
            "avg_volume": _f(quote.get("average_volume"), _f(quote.get("volume"))),
            "rsi": rsi, "macd": macd_last, "macd_signal": macd_sig, "macd_prev": macd_prev,
            "bb_pos": bb_pos, "change_5d": change_5d,
            "closes": closes,
            "mom_12_1": ind.momentum_12_1(closes),
            "volatility": ind.annualized_volatility(closes),
        }

    # --- Alpha Vantage: 펀더멘털 & 목표가 ----------------------------------
    def _fundamentals(self, ticker: str) -> dict:
        ov = self._get(self.AV_BASE, {"function": "OVERVIEW", "symbol": ticker, "apikey": self.alpha_key})
        # ROE/마진은 소수(0.15) → %로 환산
        result = {
            "per": _f(ov.get("PERatio")),
            "pbr": _f(ov.get("PriceToBookRatio")),
            "roe": _f(ov.get("ReturnOnEquityTTM")) * 100,
            "op_margin": _f(ov.get("OperatingMarginTTM")) * 100,
            "target": _f(ov.get("AnalystTargetPrice")),
            "sector": ov.get("Sector", ""),
        }
        try:
            inc = self._get(self.AV_BASE, {"function": "INCOME_STATEMENT",
                                           "symbol": ticker, "apikey": self.alpha_key})
            q = inc.get("quarterlyReports", []) or []          # 최신이 [0]
            result["revenue"] = [_f(r.get("totalRevenue")) for r in q[:8]]
            result["op_income"] = [_f(r.get("operatingIncome")) for r in q[:8]]
        except Exception as e:
            log.warning("[US] %s 손익 조회 실패: %s", ticker, e)
            result["revenue"], result["op_income"] = [], []
        return result

    # --- Finnhub: 뉴스 건수 -------------------------------------------------
    def _news_count(self, ticker: str) -> int:
        if not self.finnhub_key:
            return 0
        today = dt.date.today()
        week_ago = today - dt.timedelta(days=7)
        try:
            news = self._get(f"{self.FH_BASE}/company-news",
                             {"symbol": ticker, "from": week_ago.isoformat(),
                              "to": today.isoformat(), "token": self.finnhub_key})
            return len(news) if isinstance(news, list) else 0
        except Exception as e:
            log.warning("[US] %s 뉴스 조회 실패: %s", ticker, e)
            return 0

    # --- 조립 ---------------------------------------------------------------
    def fetch_universe(self) -> list[Stock]:
        if not (self.alpha_key or self.twelve_key):
            log.info("[US] 키 없음 → Mock 데이터 사용")
            return MockDataSource("US").fetch_universe()

        raw = []
        for ticker, name, themes in self.universe:
            try:
                tech = self._tech(ticker) if self.twelve_key else {}
                fund = self._fundamentals(ticker) if self.alpha_key else {}
                news = self._news_count(ticker)
                raw.append((ticker, name, themes, tech, fund, news))
            except Exception as e:
                log.warning("[US] %s 수집 실패: %s", ticker, e)

        if not raw:
            log.error("[US] 실데이터 전체 실패 → Mock 폴백")
            return MockDataSource("US").fetch_universe()

        # 섹터 평균 PER/PBR
        per_by_sector, pbr_by_sector = defaultdict(list), defaultdict(list)
        for _, _, _, _, fund, _ in raw:
            sec = fund.get("sector", "")
            if fund.get("per", 0) > 0:
                per_by_sector[sec].append(fund["per"])
            if fund.get("pbr", 0) > 0:
                pbr_by_sector[sec].append(fund["pbr"])

        def avg(xs):
            return sum(xs) / len(xs) if xs else 0.0

        stocks = []
        for ticker, name, themes, tech, fund, news in raw:
            sec = fund.get("sector", "")
            price = tech.get("price", 0.0)
            stocks.append(Stock(
                ticker=ticker, name=name, market="US", currency="USD",
                financial=FinancialData(
                    per=fund.get("per", 0.0), pbr=fund.get("pbr", 0.0),
                    sector_per=avg(per_by_sector[sec]) or fund.get("per", 0.0),
                    sector_pbr=avg(pbr_by_sector[sec]) or fund.get("pbr", 0.0),
                    roe=fund.get("roe", 0.0), operating_margin=fund.get("op_margin", 0.0),
                    debt_ratio=0.0,
                    revenue_quarters=fund.get("revenue", []),
                    op_income_quarters=fund.get("op_income", []),
                ),
                tech=TechData(
                    current_price=price,
                    volume=tech.get("volume", 0.0), avg_volume_20d=tech.get("avg_volume", 1.0),
                    price_change_5d=tech.get("change_5d", 0.0),
                    rsi_14=tech.get("rsi", 50.0),
                    macd=tech.get("macd", 0.0), macd_signal=tech.get("macd_signal", 0.0),
                    macd_prev_diff=tech.get("macd_prev", 0.0),
                    bb_position=tech.get("bb_pos", 0.5),
                    ma20=price, ma60=price,
                    # LIVE: Twelve Data 일봉으로 중기 모멘텀·변동성 계산
                    mom_12_1=tech.get("mom_12_1"),
                    volatility=tech.get("volatility"),
                    closes=tech.get("closes", []),
                ),
                sentiment=SentimentData(
                    news_count_today=news, avg_news_count=5.0,
                    sentiment_score=0.0, sentiment_prev=0.0,   # TODO: 뉴스 본문 감성분석
                ),
                analyst=AnalystData(
                    target_mean=fund.get("target", 0.0),
                    num_analysts=5 if fund.get("target", 0) > 0 else 0,  # AV는 인원수 미제공
                ),
                theme=ThemeData(themes=themes, theme_volume_surge=1.0, sector_strength_pct=50.0),
                beneficiary=BeneficiaryData(),
                blog=BlogData(),
                # TODO(데이터 연동): quality(Alpha Vantage BALANCE_SHEET+CASH_FLOW 또는 FMP →
                #   F-Score/FCF/ROIC/Altman/Accruals), analyst_ext(Finnhub 추정치·서프라이즈),
                #   insider(Finnhub Form4), red_flag
            ))
        log.info("[US] %d/%d 종목 수집 완료", len(stocks), len(self.universe))
        return stocks
