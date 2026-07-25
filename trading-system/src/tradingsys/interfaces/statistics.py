"""Statistics Engine contract.

Computes performance metrics from the trader's OWN journal — never internet win
rates. Slices by strategy, session, time-of-day, volatility regime, news
condition, and day-of-week so edges can be located, not assumed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence, runtime_checkable

from ..domain.types import PerformanceMetrics


@runtime_checkable
class StatisticsEngine(Protocol):
    def overall(
        self, account_id: int, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> PerformanceMetrics:
        """Aggregate metrics: win rate, expectancy, profit factor, drawdown…"""
        ...

    def by_scope(
        self,
        account_id: int,
        scope: str,   # 'by_strategy'|'by_session'|'by_time_of_day'|'by_volatility'|...
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Sequence[PerformanceMetrics]:
        """One metrics record per bucket within the requested scope."""
        ...

    def has_sufficient_sample(self, account_id: int, scope: str, scope_key: str) -> bool:
        """True when own-data sample is large enough to trust over external priors."""
        ...
