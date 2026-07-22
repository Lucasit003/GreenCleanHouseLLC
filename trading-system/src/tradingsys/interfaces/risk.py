"""Risk Management Engine contract — the highest-priority module.

The Risk Engine holds **hard veto power** over every recommendation. It sizes
positions, enforces max daily loss / drawdown / trade-count / exposure limits,
and encodes the account's prop-firm rules. Nothing downstream may bypass it.

Core risk rules are SACRED: this interface exposes no method that mutates rules
without an explicit, human-supplied approver. Automated rule changes are
impossible by construction — the Learning Engine can only *propose*.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from ..domain.types import AccountState, RiskDecision, RiskRules, Setup


@runtime_checkable
class RiskEngine(Protocol):
    def active_rules(self, account_id: int) -> RiskRules:
        """Return the currently active, human-approved rule set."""
        ...

    def position_size(
        self, setup: Setup, account: AccountState, rules: RiskRules
    ) -> int:
        """Contracts to trade given risk-per-trade and stop distance. May be 0."""
        ...

    def evaluate(self, setup: Setup, account: AccountState) -> RiskDecision:
        """Approve or VETO a setup. Records every check.

        Returns ``approved=False`` with ``veto_reasons`` whenever any rule would
        be breached (daily loss hit, trade limit reached, drawdown, exposure,
        oversize, etc.). This result is authoritative and cannot be overridden
        downstream.
        """
        ...

    def propose_rule_change(self, new_rules: RiskRules, proposed_by: str) -> int:
        """Queue a rule change for HUMAN approval. Never applies it. Returns id."""
        ...

    def approve_rule_change(
        self, version: int, approved_by: str, max_daily_loss: Decimal | None = None
    ) -> RiskRules:
        """Apply a queued rule change — requires a human ``approved_by``."""
        ...
