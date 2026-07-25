"""EMA-cross momentum strategy.

Thesis: when a fast EMA crosses a slow EMA, momentum has shifted. A pure
trend-follower — expected to shine in trends and get chopped up in ranges.
Measured, not assumed.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from ....domain.types import Bar, Direction, MarketContext, Setup, Trend
from ....indicators import ema


class EmaCrossStrategy:
    key = "ema_cross"
    name = "EMA Cross Momentum"

    def __init__(self, fast: int = 9, slow: int = 21, rr: float = 2.0, stop_atr_mult: float = 1.5) -> None:
        self._fast, self._slow, self._rr, self._stop_mult = fast, slow, rr, stop_atr_mult

    def ideal_conditions(self) -> Mapping[str, object]:
        return {"trend": "developing", "volatility": "normal"}

    def poor_conditions(self) -> Mapping[str, object]:
        return {"trend": "range", "note": "whipsaw crosses in chop"}

    def find_setups(self, context: MarketContext, bars: Sequence[Bar]) -> Sequence[Setup]:
        if context.atr is None:
            return []
        closes = [float(b.close) for b in bars]
        f = ema(closes, self._fast)
        s = ema(closes, self._slow)
        if len(closes) < self._slow + 2 or f[-1] != f[-1] or f[-2] != f[-2]:
            return []

        last = bars[-1]
        atr = context.atr
        entry = last.close
        crossed_up = f[-2] <= s[-2] and f[-1] > s[-1]
        crossed_down = f[-2] >= s[-2] and f[-1] < s[-1]

        if crossed_up and context.trend is not Trend.BEAR:
            stop = entry - atr * Decimal(str(self._stop_mult))
            target = entry + (entry - stop) * Decimal(str(self._rr))
            direction = Direction.LONG
        elif crossed_down and context.trend is not Trend.BULL:
            stop = entry + atr * Decimal(str(self._stop_mult))
            target = entry - (stop - entry) * Decimal(str(self._rr))
            direction = Direction.SHORT
        else:
            return []

        return [Setup(
            strategy_key=self.key, instrument=context.instrument, direction=direction,
            proposed_entry=entry, proposed_stop=stop, proposed_target=target,
            rationale=f"EMA{self._fast}/{self._slow} cross {direction.value}",
            detected_at=last.ts, reward_risk=self._rr, market_context=context,
        )]
