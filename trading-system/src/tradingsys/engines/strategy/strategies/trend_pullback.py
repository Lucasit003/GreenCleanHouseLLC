"""Trend-pullback strategy.

Thesis: in an established trend, a pullback to a moving average that then resumes
is a higher-quality entry than chasing. This is a *hypothesis* the system
measures — its confidence comes from the trader's own results, not this comment.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from ....domain.types import Bar, Direction, MarketContext, Setup, Trend
from ....indicators import ema


class TrendPullbackStrategy:
    key = "trend_pullback"
    name = "Trend Pullback to EMA"

    def __init__(self, ema_period: int = 21, rr: float = 2.0, stop_atr_mult: float = 1.0) -> None:
        self._ema = ema_period
        self._rr = rr
        self._stop_mult = stop_atr_mult

    def ideal_conditions(self) -> Mapping[str, object]:
        return {"trend": "bull or bear", "structure": "trend_continuation", "volatility": "normal"}

    def poor_conditions(self) -> Mapping[str, object]:
        return {"trend": "range", "volatility": "high", "note": "chop causes false pullbacks"}

    def find_setups(self, context: MarketContext, bars: Sequence[Bar]) -> Sequence[Setup]:
        if context.trend not in (Trend.BULL, Trend.BEAR) or context.atr is None:
            return []
        closes = [float(b.close) for b in bars]
        ema_series = ema(closes, self._ema)
        if ema_series[-1] != ema_series[-1]:  # NaN guard
            return []

        last = bars[-1]
        ema_val = Decimal(str(round(ema_series[-1], 4)))
        atr = context.atr
        entry = last.close

        if context.trend is Trend.BULL:
            # price pulled back near/below EMA then closed back above it
            pulled_back = last.low <= ema_val and last.close > ema_val
            if not pulled_back:
                return []
            stop = ema_val - atr * Decimal(str(self._stop_mult))
            risk = entry - stop
            if risk <= 0:
                return []
            target = entry + risk * Decimal(str(self._rr))
            direction = Direction.LONG
        else:
            pulled_back = last.high >= ema_val and last.close < ema_val
            if not pulled_back:
                return []
            stop = ema_val + atr * Decimal(str(self._stop_mult))
            risk = stop - entry
            if risk <= 0:
                return []
            target = entry - risk * Decimal(str(self._rr))
            direction = Direction.SHORT

        return [Setup(
            strategy_key=self.key, instrument=context.instrument, direction=direction,
            proposed_entry=entry, proposed_stop=stop, proposed_target=target,
            rationale=f"{context.trend.value} trend pullback to EMA{self._ema}; resumed in trend direction",
            detected_at=last.ts, reward_risk=self._rr, market_context=context,
        )]
