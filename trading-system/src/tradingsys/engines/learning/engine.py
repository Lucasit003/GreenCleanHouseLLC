"""Learning Engine (Step 12).

Updates per-strategy confidence from the trader's OWN long-term results, with an
explicit overfitting guard: confidence is shrunk toward a neutral prior in
proportion to how little evidence exists, so a short lucky/unlucky streak cannot
swing it. It never assumes a strategy is permanently good or bad.

HARD BOUNDARY: this engine only *proposes*. It can never change risk rules — a
``risk_change`` proposal always carries ``requires_human_approval=True`` and is
applied only by a human through the Risk Engine.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from ...domain.types import Confidence, LearningProposal, TradeResult
from ...interfaces.repository import TradeRepository

_PRIOR = 0.5           # neutral belief before evidence
_MIN_SAMPLE = 40       # shrinkage strength; mirrors config learning.min_sample


class LearningEngine:
    def __init__(self, trades: TradeRepository, account_id: int) -> None:
        self._trades = trades
        self._account_id = account_id
        self._history: dict[str, list[Confidence]] = {}

    def _closed(self, strategy_key: str):
        return [
            t for t in self._trades.query(self._account_id, strategy_key=strategy_key)
            if t.result in (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN)
            and t.net_pnl is not None
        ]

    def update_confidence(self, strategy_key: str) -> Confidence:
        closed = self._closed(strategy_key)
        n = len(closed)
        wins = sum(1 for t in closed if t.result is TradeResult.WIN)
        # Shrinkage toward the prior: (wins + prior*k) / (n + k).
        value = (wins + _PRIOR * _MIN_SAMPLE) / (n + _MIN_SAMPLE)
        method = "shrunk_win_rate(prior=0.5,k=%d)" % _MIN_SAMPLE
        conf = Confidence(
            strategy_key=strategy_key, value=round(value, 4), sample_size=n,
            method=method, as_of=datetime.now(timezone.utc),
        )
        self._history.setdefault(strategy_key, []).append(conf)
        return conf

    def confidence_history(self, strategy_key: str, limit: int = 100) -> Sequence[Confidence]:
        return self._history.get(strategy_key, [])[-limit:]

    def review(self, account_id: int) -> Sequence[LearningProposal]:
        proposals: list[LearningProposal] = []
        strategy_keys = {
            t.strategy_key for t in self._trades.query(account_id) if t.strategy_key
        }
        for key in sorted(strategy_keys):
            conf = self.update_confidence(key)
            proposals.append(LearningProposal(
                kind="confidence_update", target=key,
                payload={"confidence": conf.value, "method": conf.method},
                evidence_sample=conf.sample_size, created_at=conf.as_of,
                requires_human_approval=False,
            ))
            # If a strategy shows a persistently negative edge over a MEANINGFUL
            # sample, suggest disabling it — for human review only.
            closed = self._closed(key)
            if len(closed) >= _MIN_SAMPLE:
                net = sum((float(t.net_pnl) for t in closed), 0.0)
                if net < 0:
                    proposals.append(LearningProposal(
                        kind="flag", target=key,
                        payload={"suggestion": "review/disable", "net_pnl": net,
                                 "reason": "negative edge over meaningful sample"},
                        evidence_sample=len(closed), created_at=datetime.now(timezone.utc),
                        requires_human_approval=True,
                    ))
        return proposals
