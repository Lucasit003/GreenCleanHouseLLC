"""Market Analysis Engine contract.

Turns raw bars into a labeled ``MarketContext`` (trend, structure, volatility
regime, session, key levels). This is the explainability substrate: every field
is a cited observation, never an opaque signal.
"""
from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from ..domain.types import Bar, MarketContext


@runtime_checkable
class MarketAnalysisEngine(Protocol):
    def analyze(self, symbol: str, timeframe: str, bars: Sequence[Bar]) -> MarketContext:
        """Produce a labeled market context from a window of bars.

        Implementations must populate every structural label they can justify
        and leave the rest as ``UNKNOWN`` rather than guessing — acknowledging
        uncertainty is a valid, required output.
        """
        ...
