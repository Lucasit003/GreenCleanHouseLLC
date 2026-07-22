"""Statistics Engine v1 implementation (Step 3).

Computes metrics from the trader's OWN closed trades — win rate, avg
winner/loser, expectancy, profit factor, max drawdown — and slices them by
strategy / session / time-of-day. No internet win rates.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Optional, Sequence

from ...domain.types import PerformanceMetrics, Trade, TradeResult
from ...interfaces.repository import TradeRepository

_MIN_SAMPLE = 30  # mirrors config: analytics.min_sample_for_own_data


def _closed(trades: Sequence[Trade]) -> list[Trade]:
    return [t for t in trades if t.result != TradeResult.OPEN and t.net_pnl is not None]


def _metrics(scope: str, scope_key: Optional[str], trades: Sequence[Trade]) -> PerformanceMetrics:
    closed = _closed(trades)
    n = len(closed)
    if n == 0:
        return PerformanceMetrics(scope=scope, scope_key=scope_key, sample_size=0)

    wins = [t for t in closed if t.result == TradeResult.WIN]
    losses = [t for t in closed if t.result == TradeResult.LOSS]
    gross_win = sum((t.net_pnl for t in wins), Decimal("0"))
    gross_loss = sum((t.net_pnl for t in losses), Decimal("0"))  # negative

    win_rate = len(wins) / n
    avg_winner = (gross_win / len(wins)).quantize(Decimal("0.01")) if wins else None
    avg_loser = (gross_loss / len(losses)).quantize(Decimal("0.01")) if losses else None
    net_total = sum((t.net_pnl for t in closed), Decimal("0"))
    expectancy = (net_total / n).quantize(Decimal("0.0001"))
    profit_factor = float(gross_win / -gross_loss) if gross_loss < 0 else None

    # Max drawdown over the equity curve (trade-sequenced).
    equity = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")
    for t in sorted(closed, key=lambda x: x.exit_time or x.entry_time):
        equity += t.net_pnl or Decimal("0")
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    # Average hold time (minutes).
    holds = [
        (t.exit_time - t.entry_time).total_seconds() / 60
        for t in closed
        if t.exit_time is not None
    ]
    avg_hold = sum(holds) / len(holds) if holds else None

    return PerformanceMetrics(
        scope=scope,
        scope_key=scope_key,
        sample_size=n,
        win_rate=round(win_rate, 4),
        avg_winner=avg_winner,
        avg_loser=avg_loser,
        expectancy=expectancy,
        profit_factor=round(profit_factor, 4) if profit_factor is not None else None,
        max_drawdown=max_dd.quantize(Decimal("0.01")),
        avg_hold_min=round(avg_hold, 2) if avg_hold is not None else None,
    )


class StatisticsEngine:
    def __init__(self, trades: TradeRepository) -> None:
        self._trades = trades

    def overall(
        self, account_id: int, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> PerformanceMetrics:
        trades = self._trades.query(account_id, start=start, end=end)
        return _metrics("overall", None, trades)

    def by_scope(
        self,
        account_id: int,
        scope: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Sequence[PerformanceMetrics]:
        trades = self._trades.query(account_id, start=start, end=end)
        keyer = _SCOPE_KEYS.get(scope)
        if keyer is None:
            raise ValueError(f"unknown scope: {scope}")
        buckets: dict[str, list[Trade]] = {}
        for t in trades:
            key = keyer(t)
            if key is not None:
                buckets.setdefault(key, []).append(t)
        return [_metrics(scope, key, ts) for key, ts in sorted(buckets.items())]

    def has_sufficient_sample(self, account_id: int, scope: str, scope_key: str) -> bool:
        for m in self.by_scope(account_id, scope):
            if m.scope_key == scope_key:
                return m.sample_size >= _MIN_SAMPLE
        return False


def _time_of_day(t: Trade) -> Optional[str]:
    return f"{t.entry_time.hour:02d}:00"


_SCOPE_KEYS: dict[str, Callable[[Trade], Optional[str]]] = {
    "by_strategy": lambda t: t.strategy_key,
    "by_session": lambda t: t.session.value if t.session else None,
    "by_time_of_day": _time_of_day,
    "by_weekday": lambda t: t.entry_time.strftime("%A"),
}
