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
