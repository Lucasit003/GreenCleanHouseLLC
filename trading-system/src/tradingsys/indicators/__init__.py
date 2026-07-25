"""Pure indicator functions (Step 6).

Each is a standalone, independently testable function operating on plain floats
(prices are converted from Decimal by the caller). Keeping these pure — no I/O,
no state — is what lets us unit-test them against known reference values and
decide, per the brief, when an indicator adds information vs. noise.
"""
from __future__ import annotations

from typing import Sequence


def sma(values: Sequence[float], period: int) -> list[float]:
    """Simple moving average. Output aligns to input; leading entries are NaN."""
    out: list[float] = []
    for i in range(len(values)):
        if i + 1 < period:
            out.append(float("nan"))
        else:
            window = values[i + 1 - period : i + 1]
            out.append(sum(window) / period)
    return out


def ema(values: Sequence[float], period: int) -> list[float]:
    """Exponential moving average, seeded with the first SMA(period)."""
    out: list[float] = [float("nan")] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int) -> list[float]:
    """Average True Range (Wilder). Output aligns to input; leading NaN."""
    n = len(closes)
    out: list[float] = [float("nan")] * n
    if n <= period:
        return out
    trs = [float("nan")]
    for i in range(1, n):
        trs.append(true_range(highs[i], lows[i], closes[i - 1]))
    first = sum(trs[1 : period + 1]) / period
    out[period] = first
    prev = first
    for i in range(period + 1, n):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i] = prev
    return out


def rsi(values: Sequence[float], period: int = 14) -> list[float]:
    n = len(values)
    out: list[float] = [float("nan")] * n
    if n <= period:
        return out
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, n):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def vwap(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], volumes: Sequence[float]) -> list[float]:
    """Cumulative VWAP over the provided window (typical price weighted)."""
    out: list[float] = []
    cum_pv, cum_v = 0.0, 0.0
    for h, l, c, v in zip(highs, lows, closes, volumes):
        typical = (h + l + c) / 3
        cum_pv += typical * v
        cum_v += v
        out.append(cum_pv / cum_v if cum_v else float("nan"))
    return out
