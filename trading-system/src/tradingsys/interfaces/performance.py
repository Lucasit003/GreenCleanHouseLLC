"""Performance Review Engine contract.

Runs periodic reviews over the journal + analytics to detect behavioral
patterns (overtrading, revenge trading, FOMO, deviation from plan) and recommend
corrective actions. This is the trading-psychology coach.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

from ..domain.types import BehaviorFlag


@runtime_checkable
class PerformanceReviewEngine(Protocol):
    def review(
        self, account_id: int, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> Sequence[BehaviorFlag]:
        """Detect behavioral patterns and emit flags with corrective advice."""
        ...

    def summary(self, account_id: int, period: str = "week") -> dict[str, Any]:
        """A human-readable review summary (metrics + flags + coaching notes)."""
        ...
