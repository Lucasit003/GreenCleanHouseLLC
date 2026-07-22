"""Market data provider contract.

Every data vendor (Databento, Polygon, broker feed, …) is an *adapter*
implementing this Protocol. Engines depend on the interface, never the vendor,
so a vendor swap is a new adapter — not an engine change.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator, Protocol, Sequence, runtime_checkable

from ..domain.types import Bar, Instrument


@runtime_checkable
class MarketDataProvider(Protocol):
    """Historical + streaming market data, normalized to the ``Bar`` type."""

    def get_history(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> Sequence[Bar]:
        """Return historical bars in ascending time order."""
        ...

    def stream(self, symbol: str, timeframe: str) -> Iterator[Bar]:
        """Yield bars as they close, in real time. Blocks/awaits per adapter."""
        ...

    def get_instrument_spec(self, symbol: str) -> Instrument:
        """Return contract specification (tick size/value, sessions, margin)."""
        ...
