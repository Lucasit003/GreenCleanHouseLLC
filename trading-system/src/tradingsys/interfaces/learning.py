"""Learning Engine contract.

Updates per-strategy confidence from LONG-TERM evidence, with overfitting guards
(minimum sample size, walk-forward, decay). It never assumes a strategy is
permanently good or bad — confidence rises and falls with measured results.

CRITICAL BOUNDARY: the Learning Engine may never change risk rules. It can only
emit ``LearningProposal`` objects; risk changes carry
``requires_human_approval=True`` and are applied only by a human via the Risk
Engine.
"""
from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from ..domain.types import Confidence, LearningProposal


@runtime_checkable
class LearningEngine(Protocol):
    def update_confidence(self, strategy_key: str) -> Confidence:
        """Recompute a strategy's confidence from its own realized track record.

        Must include ``sample_size`` and ``method``; must apply overfitting
        guards and refuse to over-react to a small recent run of outcomes.
        """
        ...

    def review(self, account_id: int) -> Sequence[LearningProposal]:
        """Produce proposals (confidence updates, flags, and — for human review
        only — risk-change suggestions). Never applies risk changes itself.
        """
        ...

    def confidence_history(self, strategy_key: str, limit: int = 100) -> Sequence[Confidence]:
        """Return the confidence trajectory so it can be audited for overfitting."""
        ...
