"""Paper (simulated) Execution Engine.

The default execution adapter. Fills are simulated at the recommendation's
entry price; no real orders leave the process. Used by backtesting, by live
shadowing, and — importantly — by autonomous trading until a human deliberately
promotes autonomy to a live adapter.

Safety invariants enforced here (identical for the future live adapter):
  * refuses to submit unless ``risk_decision.approved`` is True;
  * refuses unless the ``Authorization`` is valid (human with an actor, or
    autonomous with a policy_version AND an armed_by human).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ...domain.types import (
    AccountState,
    Authorization,
    AuthorizationKind,
    Recommendation,
    RecommendationAction,
    RiskDecision,
    Trade,
)


def _validate_authorization(auth: Authorization) -> None:
    if auth.kind is AuthorizationKind.HUMAN:
        if not auth.actor:
            raise PermissionError("human authorization requires an actor")
    elif auth.kind is AuthorizationKind.AUTONOMOUS:
        if auth.policy_version is None or not auth.armed_by:
            raise PermissionError(
                "autonomous authorization requires an armed policy_version and armed_by human"
            )
    else:  # pragma: no cover - exhaustive
        raise PermissionError(f"unknown authorization kind: {auth.kind}")


class PaperExecutionEngine:
    def __init__(self, account: AccountState) -> None:
        self._account = account

    @property
    def is_paper(self) -> bool:
        return True

    def account_state(self, account_id: int) -> AccountState:
        return self._account

    def submit(
        self,
        recommendation: Recommendation,
        risk_decision: RiskDecision,
        authorization: Authorization,
    ) -> Trade:
        if recommendation.action is not RecommendationAction.ENTER:
            raise ValueError("only ENTER recommendations can be submitted")
        if not risk_decision.approved:
            raise PermissionError(f"risk vetoed: {risk_decision.veto_reasons}")
        _validate_authorization(authorization)

        setup = recommendation.setup
        assert setup is not None and recommendation.direction is not None
        size = risk_decision.computed_size or recommendation.suggested_size or 0
        if size < 1:
            raise ValueError("computed size below 1 contract")

        trade = Trade(
            account_id=recommendation.account_id,
            instrument=setup.instrument,
            direction=recommendation.direction,
            quantity=size,
            entry_time=recommendation.created_at,
            entry_price=recommendation.entry or setup.proposed_entry,
            is_paper=True,
            stop_price=recommendation.stop or setup.proposed_stop,
            target_price=recommendation.target or setup.proposed_target,
            strategy_key=setup.strategy_key,
            setup_id=setup.id,
            recommendation_id=recommendation.id,
            risk_amount=risk_decision.risk_amount,
            session=setup.market_context.session if setup.market_context else None,
            entry_reason=setup.rationale,
            tags=[f"auth:{authorization.kind.value}"],
        )
        # reflect the new open position in the paper account
        self._account = AccountState(
            account_id=self._account.account_id,
            balance=self._account.balance,
            open_positions=self._account.open_positions + 1,
            daily_pnl=self._account.daily_pnl,
            daily_trades=self._account.daily_trades + 1,
            weekly_pnl=self._account.weekly_pnl,
            current_drawdown=self._account.current_drawdown,
            is_paper=True,
        )
        return trade

    def flatten(self, account_id: int, reason: str) -> None:
        self._account = AccountState(
            account_id=self._account.account_id,
            balance=self._account.balance,
            open_positions=0,
            daily_pnl=self._account.daily_pnl,
            daily_trades=self._account.daily_trades,
            weekly_pnl=self._account.weekly_pnl,
            current_drawdown=self._account.current_drawdown,
            is_paper=True,
        )

    def broker_info(self) -> dict[str, Any]:
        return {"broker": "paper", "is_paper": True, "note": "simulated fills at entry price"}
