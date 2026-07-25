"""Range-breakout strategy.

Thesis: a close beyond a recent consolidation high/low, on expanding range, can
mark the start of a directional move. Again — a hypothesis to be measured, not a
belief. It deliberately stands down in already-extended, high-volatility states
to avoid buying the top of a spike.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from ....domain.types import (
    Bar,
    Direction,
    MarketContext,
    Setup,
    Structure,
    VolatilityRegime,
)


class BreakoutStrategy:
    key = "breakout"
    name = "Range Breakout"

    def __init__(self, lookback: int = 20, rr: float = 2.0, stop_atr_mult: float = 1.0) -> None:
        self._lookback = lookback
        self._rr = rr
        self._stop_mult = stop_atr_mult

    def ideal_conditions(self) -> Mapping[str, object]:
        return {"structure": "breakout", "volatility": "normal", "note": "fresh break, not extended"}

    def poor_conditions(self) -> Mapping[str, object]:
        return {"volatility": "high", "note": "chasing an extended spike -> failed breakouts"}

    def find_setups(self, context: MarketContext, bars: Sequence[Bar]) -> Sequence[Setup]:
        if context.structure is not Structure.BREAKOUT or context.atr is None:
            return []
        if context.volatility_regime is VolatilityRegime.HIGH:
            return []  # stand down when already extended

        window = bars[-min(len(bars), self._lookback):-1]
        if not window:
            return []
        prior_high = max(b.high for b in window)
        prior_low = min(b.low for b in window)
        last = bars[-1]
        atr = context.atr
        entry = last.close

        if last.close > prior_high:
            stop = entry - atr * Decimal(str(self._stop_mult))
            risk = entry - stop
            target = entry + risk * Decimal(str(self._rr))
            direction = Direction.LONG
            desc = f"close broke {self._lookback}-bar high {prior_high}"
        elif last.close < prior_low:
            stop = entry + atr * Decimal(str(self._stop_mult))
            risk = stop - entry
            target = entry - risk * Decimal(str(self._rr))
            direction = Direction.SHORT
            desc = f"close broke {self._lookback}-bar low {prior_low}"
        else:
            return []

        if risk <= 0:
            return []
        return [Setup(
            strategy_key=self.key, instrument=context.instrument, direction=direction,
            proposed_entry=entry, proposed_stop=stop, proposed_target=target,
            rationale=f"range breakout: {desc}", detected_at=last.ts,
            reward_risk=self._rr, market_context=context,
        )]
