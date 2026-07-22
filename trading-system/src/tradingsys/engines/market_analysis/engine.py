"""Market Analysis Engine (Step 6).

Turns a window of bars into a labeled ``MarketContext``: trend, structure,
volatility regime, session, ATR, and key levels. Every label is justifiable and
genuine ambiguity is reported as ``UNKNOWN`` rather than guessed — acknowledging
uncertainty is a required output.
"""
from __future__ import annotations

from decimal import Decimal
from statistics import median
from typing import Sequence

from ...domain.types import (
    Bar,
    KeyLevel,
    MarketContext,
    Session,
    Structure,
    Trend,
    VolatilityRegime,
)
from ...indicators import atr, ema


def session_for(hour_utc: int) -> Session:
    """Approximate CME futures session from a UTC hour (documented heuristic)."""
    if 0 <= hour_utc < 6:
        return Session.ASIA
    if 6 <= hour_utc < 13:
        return Session.LONDON
    if 13 <= hour_utc < 17:
        return Session.NY_AM
    if 17 <= hour_utc < 21:
        return Session.NY_PM
    return Session.OVERNIGHT


class MarketAnalysisEngine:
    def __init__(self, fast: int = 9, slow: int = 21, atr_period: int = 14) -> None:
        self._fast, self._slow, self._atr_period = fast, slow, atr_period

    def analyze(self, symbol: str, timeframe: str, bars: Sequence[Bar]) -> MarketContext:
        last = bars[-1]
        if len(bars) < self._slow + 2:
            return MarketContext(
                instrument=symbol, timeframe=timeframe, ts=last.ts,
                trend=Trend.RANGE, structure=Structure.UNKNOWN,
                volatility_regime=VolatilityRegime.NORMAL,
                session=session_for(last.ts.hour),
                factors={"reason": "insufficient bars for reliable analysis"},
            )

        closes = [float(b.close) for b in bars]
        highs = [float(b.high) for b in bars]
        lows = [float(b.low) for b in bars]

        ema_fast = ema(closes, self._fast)
        ema_slow = ema(closes, self._slow)
        atr_series = atr(highs, lows, closes, self._atr_period)
        cur_atr = atr_series[-1]

        # --- trend: EMA relationship + confirmation from close ---
        f, s, c = ema_fast[-1], ema_slow[-1], closes[-1]
        if f > s and c > s:
            trend = Trend.BULL
        elif f < s and c < s:
            trend = Trend.BEAR
        else:
            trend = Trend.RANGE

        # --- volatility regime: current ATR vs its recent median ---
        valid_atr = [a for a in atr_series if a == a]  # drop NaN
        med = median(valid_atr) if valid_atr else cur_atr
        if med and cur_atr > 1.3 * med:
            vol = VolatilityRegime.HIGH
        elif med and cur_atr < 0.7 * med:
            vol = VolatilityRegime.LOW
        else:
            vol = VolatilityRegime.NORMAL

        # --- key levels: recent swing high/low ---
        window = bars[-min(len(bars), 20):]
        swing_high = max(window, key=lambda b: b.high).high
        swing_low = min(window, key=lambda b: b.low).low
        levels = (
            KeyLevel(price=swing_high, kind="resistance", strength=0.6),
            KeyLevel(price=swing_low, kind="support", strength=0.6),
        )

        # --- structure: breakout / range / trend continuation ---
        prior_high = max(b.high for b in bars[-min(len(bars), 20):-1])
        prior_low = min(b.low for b in bars[-min(len(bars), 20):-1])
        if last.close > prior_high:
            structure = Structure.BREAKOUT
        elif last.close < prior_low:
            structure = Structure.BREAKOUT
        elif trend in (Trend.BULL, Trend.BEAR):
            structure = Structure.TREND_CONTINUATION
        elif vol is VolatilityRegime.LOW:
            structure = Structure.ACCUMULATION
        else:
            structure = Structure.UNKNOWN

        return MarketContext(
            instrument=symbol, timeframe=timeframe, ts=last.ts,
            trend=trend, structure=structure, volatility_regime=vol,
            session=session_for(last.ts.hour),
            atr=Decimal(str(round(cur_atr, 4))),
            key_levels=levels,
            factors={
                "ema_fast": round(f, 4), "ema_slow": round(s, 4),
                "close": round(c, 4), "atr": round(cur_atr, 4),
                "atr_median": round(med, 4) if med else None,
                "prior_high": float(prior_high), "prior_low": float(prior_low),
            },
        )
