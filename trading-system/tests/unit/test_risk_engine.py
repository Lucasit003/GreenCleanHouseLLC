"""Risk Engine tests — the mandatory backstop for autonomous trading."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from tradingsys.domain.types import AccountState, Direction, Setup
from tradingsys.engines.risk.engine import RiskEngine


def _setup(now) -> Setup:
    # 4-point stop on ES = 16 ticks = $200 risk per contract.
    return Setup(
        strategy_key="orb", instrument="ES", direction=Direction.LONG,
        proposed_entry=Decimal("5000"), proposed_stop=Decimal("4996"),
        proposed_target=Decimal("5012"), rationale="ORB long", detected_at=now,
        reward_risk=3.0,
    )


def test_position_sizing_respects_budget_and_cap(instruments, risk_repo, flat_account, now, rules):
    engine = RiskEngine(instruments, risk_repo)
    # budget = 50000 * 0.005 = $250; $200/contract -> 1 contract.
    assert engine.position_size(_setup(now), flat_account, rules) == 1
    # Bigger account -> more contracts, but capped at max_contracts (3).
    big = replace(flat_account, balance=Decimal("500000"))
    assert engine.position_size(_setup(now), big, rules) == 3


def test_approves_clean_trade(instruments, risk_repo, flat_account, now):
    engine = RiskEngine(instruments, risk_repo)
    decision = engine.evaluate(_setup(now), flat_account)
    assert decision.approved is True
    assert decision.computed_size == 1
    assert decision.risk_amount == Decimal("200")


def test_vetoes_when_daily_loss_hit(instruments, risk_repo, flat_account, now):
    engine = RiskEngine(instruments, risk_repo)
    blown = replace(flat_account, daily_pnl=Decimal("-1000"))
    decision = engine.evaluate(_setup(now), blown)
    assert decision.approved is False
    assert any("daily loss" in r for r in decision.veto_reasons)


def test_vetoes_when_trade_limit_reached(instruments, risk_repo, flat_account, now):
    engine = RiskEngine(instruments, risk_repo)
    maxed = replace(flat_account, daily_trades=5)
    decision = engine.evaluate(_setup(now), maxed)
    assert decision.approved is False
    assert any("trade limit" in r for r in decision.veto_reasons)


def test_vetoes_when_position_already_open(instruments, risk_repo, flat_account, now):
    engine = RiskEngine(instruments, risk_repo)
    holding = replace(flat_account, open_positions=1)
    decision = engine.evaluate(_setup(now), holding)
    assert decision.approved is False
    assert any("open positions" in r for r in decision.veto_reasons)


def test_learning_cannot_change_rules_without_human(instruments, risk_repo, flat_account, now, rules):
    engine = RiskEngine(instruments, risk_repo)
    # An automated proposal is queued but NEVER active without a human approver.
    looser = replace(rules, version=2, max_daily_loss=Decimal("100000"))
    engine.propose_rule_change(looser, proposed_by="learning_engine")
    # active rules are unchanged
    assert engine.active_rules(1).max_daily_loss == Decimal("1000")
    # approving with an empty approver is refused
    import pytest
    with pytest.raises(ValueError):
        engine.approve_rule_change(2, approved_by="")
