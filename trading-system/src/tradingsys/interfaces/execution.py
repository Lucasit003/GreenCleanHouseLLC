"""Execution Engine contract.

Broker/prop-firm connectivity (Topstep first) behind one interface. Two
non-negotiable safety properties:

1. **Paper by default.** The default adapter simulates fills; live execution is
   a deliberate, human-promoted choice.
2. **No order without a passed risk decision AND human confirmation.** The
   ``submit`` method requires an approved ``RiskDecision`` and an explicit
   ``human_confirmed`` flag; implementations must reject anything else.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..domain.types import AccountState, Recommendation, RiskDecision, Trade


@runtime_checkable
class ExecutionEngine(Protocol):
    @property
    def is_paper(self) -> bool:
        """True for simulated execution. Default adapters return True."""
        ...

    def account_state(self, account_id: int) -> AccountState:
        """Live snapshot: balance, positions, daily P&L, drawdown, trade count."""
        ...

    def submit(
        self,
        recommendation: Recommendation,
        risk_decision: RiskDecision,
        *,
        human_confirmed: bool,
    ) -> Trade:
        """Place an order for an approved recommendation.

        Implementations MUST raise if ``risk_decision.approved`` is False or
        ``human_confirmed`` is False. Returns the resulting (open) ``Trade``.
        """
        ...

    def flatten(self, account_id: int, reason: str) -> None:
        """Emergency close-all — always permitted, used by risk kill-switch."""
        ...

    def broker_info(self) -> dict[str, Any]:
        """Adapter identity/capabilities (broker name, live/paper, limits)."""
        ...
