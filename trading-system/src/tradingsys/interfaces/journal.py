"""Journal Engine contract.

Records every trade with the full context needed for honest analytics: setup,
reason, entry/stop/target, exit, realized P&L, R-multiple, mistakes, lessons,
and a screenshot reference. This is the system's source of truth for the
trader's OWN performance.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Protocol, Sequence, runtime_checkable

from ..domain.types import Trade


@runtime_checkable
class JournalEngine(Protocol):
    def open_trade(self, trade: Trade) -> Trade:
        """Record a newly entered trade (result=OPEN)."""
        ...

    def close_trade(
        self,
        trade_id: int,
        exit_time: datetime,
        exit_price: Decimal,
        exit_reason: Optional[str] = None,
    ) -> Trade:
        """Close a trade; compute and persist net P&L, R-multiple, and result."""
        ...

    def annotate(
        self,
        trade_id: int,
        *,
        mistakes: Optional[str] = None,
        lessons: Optional[str] = None,
        screenshot_url: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> Trade:
        """Attach post-trade review notes."""
        ...

    def get(self, trade_id: int) -> Optional[Trade]: ...

    def history(
        self,
        account_id: int,
        *,
        strategy_key: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Sequence[Trade]: ...
