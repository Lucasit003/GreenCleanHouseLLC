"""Risk Management Engine implementation.

Pulled forward from Step 9 because autonomous execution makes the veto
mandatory: with no human clicking approve, this is the ONLY backstop between a
bad recommendation and the account. It sizes positions and holds authoritative
veto power over every setup. Core rules are sacred — this engine can *propose* a
rule change but only a human ``approve`` activates it.
"""
from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from typing import Optional

from ...domain.types import AccountState, Direction, RiskDecision, RiskRules, Setup
from ...interfaces.repository import InstrumentRepository, RiskRepository


class RiskEngine:
    def __init__(self, instruments: InstrumentRepository, risk_repo: RiskRepository) -> None:
        self._instruments = instruments
        self._risk = risk_repo

    def active_rules(self, account_id: int) -> RiskRules:
        return self._risk.active_rules(account_id)

    def _dollar_risk_per_contract(self, setup: Setup) -> Optional[Decimal]:
        instrument = self._instruments.get(setup.instrument)
        if instrument is None:
            return None
        stop_ticks = abs(setup.proposed_entry - setup.proposed_stop) / instrument.tick_size
        if stop_ticks <= 0:
            return None
        return stop_ticks * instrument.tick_value

    def position_size(self, setup: Setup, account: AccountState, rules: RiskRules) -> int:
        per_contract = self._dollar_risk_per_contract(setup)
        if per_contract is None or per_contract <= 0:
            return 0
        budget = (account.balance * rules.risk_per_trade_pct)
        size = int((budget / per_contract).to_integral_value(rounding=ROUND_DOWN))
        return max(0, min(size, rules.max_contracts))

    def evaluate(self, setup: Setup, account: AccountState) -> RiskDecision:
        rules = self._risk.active_rules(account.account_id)
        checks: dict[str, bool] = {}
        veto: list[str] = []

        # --- account-level guards (the sacred limits) ---
        daily_loss_ok = account.daily_pnl > -rules.max_daily_loss
        checks["daily_loss_within_limit"] = daily_loss_ok
        if not daily_loss_ok:
            veto.append(f"daily loss limit reached ({account.daily_pnl} <= -{rules.max_daily_loss})")

        drawdown_ok = account.current_drawdown < rules.max_drawdown
        checks["drawdown_within_limit"] = drawdown_ok
        if not drawdown_ok:
            veto.append(f"max drawdown reached ({account.current_drawdown} >= {rules.max_drawdown})")

        trades_ok = account.daily_trades < rules.max_daily_trades
        checks["daily_trade_count_ok"] = trades_ok
        if not trades_ok:
            veto.append(f"daily trade limit reached ({account.daily_trades} >= {rules.max_daily_trades})")

        exposure_ok = account.open_positions < rules.max_open_positions
        checks["open_positions_ok"] = exposure_ok
        if not exposure_ok:
            veto.append(f"max open positions reached ({account.open_positions} >= {rules.max_open_positions})")

        if rules.max_weekly_loss is not None:
            weekly_ok = account.weekly_pnl > -rules.max_weekly_loss
            checks["weekly_loss_within_limit"] = weekly_ok
            if not weekly_ok:
                veto.append(f"weekly loss limit reached ({account.weekly_pnl} <= -{rules.max_weekly_loss})")

        # --- setup-level sizing ---
        size = self.position_size(setup, account, rules)
        per_contract = self._dollar_risk_per_contract(setup)
        sizeable = size >= 1
        checks["position_sizeable"] = sizeable
        if not sizeable:
            veto.append("cannot size at least 1 contract within risk-per-trade budget")

        risk_amount = (per_contract * Decimal(size)) if (per_contract and sizeable) else None

        approved = len(veto) == 0
        decision = RiskDecision(
            approved=approved,
            risk_rule_version=rules.version,
            checks=checks,
            veto_reasons=tuple(veto),
            computed_size=size if approved else None,
            risk_amount=risk_amount if approved else None,
        )
        self._risk.record_decision(None, account.account_id, decision)
        return decision

    def propose_rule_change(self, new_rules: RiskRules, proposed_by: str) -> int:
        # NEVER activates. Queues for human approval only.
        return self._risk.propose_new_rules(new_rules, proposed_by)

    def approve_rule_change(
        self, version: int, approved_by: str, max_daily_loss: Decimal | None = None
    ) -> RiskRules:
        if not approved_by:
            raise ValueError("a human approver is required to change risk rules")
        return self._risk.approve_rules(version, approved_by)
