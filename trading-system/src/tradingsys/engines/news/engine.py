"""News Engine (Step 11).

Serves the economic calendar and computes news-risk blackout windows the
Decision Framework uses to suppress or down-weight setups around high-impact
events (FOMC, CPI, PPI, GDP, employment, Fed speakers).

``refresh`` is adapter-driven in production; here it accepts a supplied list so
the system runs offline for practice.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence

from ...domain.types import NewsEvent, NewsSeverity
from ...interfaces.repository import NewsRepository


class NewsEngine:
    def __init__(self, repo: NewsRepository, blackout_minutes: int = 15) -> None:
        self._repo = repo
        self._blackout = blackout_minutes
        # Local index so news_risk can be evaluated around an ARBITRARY time
        # (essential for backtests over historical data, not just wall-clock).
        self._events: list[NewsEvent] = []

    def load(self, events: Sequence[NewsEvent]) -> int:
        """Offline loader for practice (stands in for a vendor pull)."""
        self._events.extend(events)
        return self._repo.bulk_upsert(events)

    def refresh(self) -> int:
        # A real adapter would fetch from the provider here.
        return 0

    def upcoming(self, within_minutes: int = 120) -> Sequence[NewsEvent]:
        events = self._repo.upcoming(within_minutes)
        return sorted(events, key=lambda e: (e.severity is not NewsSeverity.HIGH, e.event_time))

    def news_risk(self, symbol: str, at: datetime) -> dict[str, Any]:
        # Evaluate events within the blackout window on either side of `at`.
        nearest_high: Optional[NewsEvent] = None
        nearest_gap = None
        next_event: Optional[NewsEvent] = None
        next_gap = None
        for e in self._events:
            gap = (e.event_time - at).total_seconds() / 60
            if abs(gap) <= self._blackout and e.severity is NewsSeverity.HIGH:
                if nearest_gap is None or abs(gap) < abs(nearest_gap):
                    nearest_high, nearest_gap = e, gap
            if gap >= 0 and (next_gap is None or gap < next_gap):
                next_event, next_gap = e, gap

        in_blackout = nearest_high is not None
        shown = nearest_high or next_event
        shown_gap = nearest_gap if nearest_high else next_gap
        return {
            "in_blackout": in_blackout,
            "next_event": shown.name if shown else None,
            "severity": shown.severity.value if shown else None,
            "minutes_until": round(shown_gap, 1) if shown_gap is not None else None,
            "blackout_window_min": self._blackout,
        }
