"""News Engine contract.

Provides the economic calendar (FOMC, CPI, PPI, GDP, employment, Fed speakers)
and computes news-risk windows the Decision Framework uses to suppress or
down-weight setups around high-impact events.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, Sequence, runtime_checkable

from ..domain.types import NewsEvent


@runtime_checkable
class NewsEngine(Protocol):
    def refresh(self) -> int:
        """Pull the latest calendar from the provider; return count upserted."""
        ...

    def upcoming(self, within_minutes: int = 120) -> Sequence[NewsEvent]:
        """High-impact-first list of events in the near future."""
        ...

    def news_risk(self, symbol: str, at: datetime) -> dict[str, Any]:
        """Assess news risk for a symbol at a moment.

        Returns a labeled dict (e.g. ``in_blackout``, ``next_event``,
        ``minutes_until``, ``severity``) so the reason is explainable.
        """
        ...
