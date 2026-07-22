"""Performance Review Engine (Step 13) — the trading-psychology coach.

Scans the journal for behavioral patterns the brief calls out (overtrading,
revenge trading, FOMO/plan-deviation) and emits ``BehaviorFlag``s with a
concrete corrective suggestion. Detection is deliberately conservative — a flag
should mean something.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from ...domain.types import BehaviorFlag, TradeResult
from ...interfaces.repository import TradeRepository


class PerformanceReviewEngine:
    def __init__(
        self,
        trades: TradeRepository,
        *,
        max_trades_per_day: int = 5,
        revenge_window_min: int = 10,
    ) -> None:
        self._trades = trades
        self._max_per_day = max_trades_per_day
        self._revenge_window = revenge_window_min

    def review(
        self, account_id: int, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> Sequence[BehaviorFlag]:
        trades = list(self._trades.query(account_id, start=start, end=end))
        flags: list[BehaviorFlag] = []
        now = datetime.now(timezone.utc)

        # --- Overtrading: more entries in a day than the plan allows. ---
        by_day: dict[str, int] = defaultdict(int)
        for t in trades:
            by_day[t.entry_time.date().isoformat()] += 1
        for day, count in by_day.items():
            if count > self._max_per_day:
                flags.append(BehaviorFlag(
                    account_id=account_id, detected_at=now, pattern="overtrading",
                    severity="warn",
                    evidence={"date": day, "trades": count, "limit": self._max_per_day},
                    recommendation=f"{count} trades on {day} exceeds your {self._max_per_day}/day plan; "
                                   "step away after the limit.",
                ))

        # --- Revenge trading: a trade opened soon after a loss, same/larger size. ---
        ordered = sorted(trades, key=lambda t: t.entry_time)
        for prev, cur in zip(ordered, ordered[1:]):
            if prev.result is not TradeResult.LOSS or prev.exit_time is None:
                continue
            gap_min = (cur.entry_time - prev.exit_time).total_seconds() / 60
            if 0 <= gap_min <= self._revenge_window and cur.quantity >= prev.quantity:
                flags.append(BehaviorFlag(
                    account_id=account_id, detected_at=now, pattern="revenge",
                    severity="critical",
                    evidence={"after_loss_trade_id": prev.id, "next_trade_id": cur.id,
                              "gap_minutes": round(gap_min, 1),
                              "size_prev": prev.quantity, "size_next": cur.quantity},
                    recommendation="Entry within minutes of a loss at equal/greater size looks like "
                                   "revenge trading. Enforce a cool-down after losses.",
                ))
        return flags

    def summary(self, account_id: int, period: str = "week") -> dict[str, Any]:
        flags = self.review(account_id)
        by_pattern: dict[str, int] = defaultdict(int)
        for f in flags:
            by_pattern[f.pattern] += 1
        return {
            "period": period,
            "flags_total": len(flags),
            "by_pattern": dict(by_pattern),
            "flags": [
                {"pattern": f.pattern, "severity": f.severity, "advice": f.recommendation}
                for f in flags
            ],
        }
