"""
기술적 지표 계산 (순수 파이썬, 표준 라이브러리만 사용).

한국투자증권 KIS는 RSI/MACD/볼린저 같은 지표를 직접 주지 않고 일봉(OHLCV)만
주므로, 종가 시계열로부터 여기서 직접 계산합니다. (미장은 Twelve Data의
내장 지표를 쓰므로 이 모듈이 필요 없습니다.)

모든 함수는 종가 리스트가 '과거→최신' 순서라고 가정합니다.
"""

from __future__ import annotations


def ema_series(values: list[float], period: int) -> list[float]:
    """지수이동평균 시계열."""
    if not values:
        return []
    k = 2.0 / (period + 1)
    ema = values[0]
    out = [ema]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
        out.append(ema)
    return out


def rsi(closes: list[float], period: int = 14) -> float:
    """Wilder 방식 RSI (0~100). 데이터 부족 시 50(중립) 반환."""
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
         ) -> tuple[float, float, float]:
    """
    MACD 반환: (macd_last, signal_last, prev_diff)
      - macd_last:  최신 MACD 라인 값
      - signal_last: 최신 시그널 라인 값
      - prev_diff:  '전일' (macd - signal). 골든크로스 판정에 사용
    """
    if len(closes) < slow + signal:
        return (0.0, 0.0, 0.0)
    ema_fast = ema_series(closes, fast)
    ema_slow = ema_series(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema_series(macd_line, signal)
    prev_diff = macd_line[-2] - signal_line[-2]
    return (macd_line[-1], signal_line[-1], prev_diff)


def bollinger_position(closes: list[float], period: int = 20, num_std: float = 2.0) -> float:
    """
    최신 종가가 볼린저밴드 내 어디에 있는지 0(하단)~1(상단)으로 반환.
    데이터 부족 시 0.5(중앙).
    """
    if len(closes) < period:
        return 0.5
    window = closes[-period:]
    mean = sum(window) / period
    var = sum((x - mean) ** 2 for x in window) / period
    std = var ** 0.5
    upper, lower = mean + num_std * std, mean - num_std * std
    if upper == lower:
        return 0.5
    pos = (closes[-1] - lower) / (upper - lower)
    return max(0.0, min(1.0, pos))


def pct_change(closes: list[float], lookback: int = 5) -> float:
    """최근 lookback 거래일 등락률(%)."""
    if len(closes) <= lookback or closes[-lookback - 1] == 0:
        return 0.0
    return (closes[-1] / closes[-lookback - 1] - 1.0) * 100.0


# ---------------------------------------------------------------------------
# 통계적 팩터용 가격 시계열 계산
# ---------------------------------------------------------------------------
def momentum_12_1(closes: list[float], skip: int = 21, lookback: int = 252,
                  min_lookback: int = 60) -> float | None:
    # min_lookback=60: KIS 일봉 100행 제한(가용≈78일)에서도 KR 모멘텀 활성화.
    #   시장 내부에서만 정규화하므로 KR(~78일)·US(~250일) 각각 일관 비교됨.
    """
    크로스섹션 모멘텀 (12-1개월) 수익률(%).

    최근 1개월(skip≈21거래일)을 제외한 과거 12개월(lookback≈252거래일) 수익률.
    직전 1개월은 단기 반전 노이즈라 빼는 것이 학술적 표준.

    데이터가 252일보다 짧으면(예: KIS 일봉 100행 제한) 가용 기간으로 lookback을
    자동 축소한다. 횡단면 정규화는 '같은 시장 내부'에서만 이뤄지므로, 시장마다
    lookback이 달라도 시장 내 비교 일관성은 유지된다. min_lookback 미만이면 None.
    """
    avail = len(closes) - 1 - skip
    if avail < min_lookback:
        return None
    lb = min(lookback, avail)
    start = closes[-(lb + skip + 1)]
    end = closes[-(skip + 1)]
    if start <= 0:
        return None
    return (end / start - 1.0) * 100.0


def annualized_volatility(closes: list[float], window: int = 120) -> float | None:
    """
    연율화 변동성(%). 최근 window 거래일의 일간수익률 표준편차 × √252.
    저변동성 이상현상(리스크 조정 랭킹)에 사용. 데이터 부족 시 None.
    """
    if len(closes) < window + 1:
        # 가능한 만큼이라도 쓰되 최소 20일은 필요
        if len(closes) < 21:
            return None
        window = len(closes) - 1
    rets = []
    seg = closes[-(window + 1):]
    for i in range(1, len(seg)):
        if seg[i - 1] > 0:
            rets.append(seg[i] / seg[i - 1] - 1.0)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return (var ** 0.5) * (252 ** 0.5) * 100.0


def _pearson(xs: list[float], ys: list[float]) -> float:
    """피어슨 상관계수. 길이 불일치/분산0 시 0."""
    n = min(len(xs), len(ys))
    if n < 3:
        return 0.0
    xs, ys = xs[-n:], ys[-n:]
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sxy / (sxx * syy) ** 0.5


def _returns(closes: list[float]) -> list[float]:
    out = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            out.append(closes[i] / closes[i - 1] - 1.0)
        else:
            out.append(0.0)
    return out


def lead_lag(own_closes: list[float], leader_closes: list[float],
             max_lag: int = 5) -> tuple[int, float]:
    """
    리드-래그 관계 추정 (그레인저 인과의 경량 프록시).

    대장주 수익률을 lag일 앞당겨 본 종목 수익률과의 상관을 최대화하는
    (best_lag, best_corr)을 반환. best_lag>0 이고 corr이 충분히 높으면
    "본 종목이 대장주를 best_lag일 시차로 따라간다"고 해석.

    동시점 상관(lag=0)보다 시차 상관이 더 높아야 '진짜 추종'으로 본다.
    """
    own_r = _returns(own_closes)
    lead_r = _returns(leader_closes)
    if len(own_r) < max_lag + 5 or len(lead_r) < max_lag + 5:
        return (0, _pearson(own_r, lead_r))
    best_lag, best_corr = 0, _pearson(own_r, lead_r)
    for lag in range(1, max_lag + 1):
        # leader(t-lag) vs own(t): leader를 lag만큼 과거로
        lead_shift = lead_r[:-lag]
        own_aligned = own_r[lag:]
        c = _pearson(own_aligned, lead_shift)
        if c > best_corr:
            best_lag, best_corr = lag, c
    return (best_lag, best_corr)
