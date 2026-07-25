"""Range-fade mean-reversion strategy.

Thesis: in a range (no trend), price tends to revert from the edges back toward
the middle. This is the OPPOSITE of the trend strategies — it should do well in
chop and poorly in trends, which makes it a useful contrast in a strategy
bake-off. Measured, not assumed.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from ....domain.types import Bar, Direction, MarketContext, Setup, Trend


class RangeFadeStrategy:
    key = "range_fade"
    name = "Range Fade (mean reversion)"

    def __init__(self, edge_atr: float = 0.5, rr: float = 1.5, stop_atr_mult: float = 1.0) -> None:
        self._edge = edge_atr        # how close to the level counts as "at the edge"
        self._rr = rr
        self._stop_mult = stop_atr_mult

    def ideal_conditions(self) -> Mapping[str, object]:
        return {"trend": "range", "structure": "accumulation", "volatility": "low/normal"}

    def poor_conditions(self) -> Mapping[str, object]:
        return {"trend": "bull or bear", "note": "fading a real trend loses"}

    def find_setups(self, context: MarketContext, bars: Sequence[Bar]) -> Sequence[Setup]:
        if context.trend is not Trend.RANGE or context.atr is None or not context.key_levels:
            return []
        atr = context.atr
        near = atr * Decimal(str(self._edge))
        last = bars[-1]
        entry = last.close

        resistance = next((l.price for l in context.key_levels if l.kind == "resistance"), None)
        support = next((l.price for l in context.key_levels if l.kind == "support"), None)

        # Fade the top: short near resistance, back toward the middle.
        if resistance is not None and abs(entry - resistance) <= near and entry <= resistance:
            stop = resistance + atr * Decimal(str(self._stop_mult))
            target = entry - (stop - entry) * Decimal(str(self._rr))
            return [Setup(
                strategy_key=self.key, instrument=context.instrument, direction=Direction.SHORT,
                proposed_entry=entry, proposed_stop=stop, proposed_target=target,
                rationale="fade range top (near resistance)", detected_at=last.ts,
                reward_risk=self._rr, market_context=context,
            )]
        # Fade the bottom: long near support.
        if support is not None and abs(entry - support) <= near and entry >= support:
            stop = support - atr * Decimal(str(self._stop_mult))
            target = entry + (entry - stop) * Decimal(str(self._rr))
            return [Setup(
                strategy_key=self.key, instrument=context.instrument, direction=Direction.LONG,
                proposed_entry=entry, proposed_stop=stop, proposed_target=target,
                rationale="fade range bottom (near support)", detected_at=last.ts,
                reward_risk=self._rr, market_context=context,
            )]
        return []
