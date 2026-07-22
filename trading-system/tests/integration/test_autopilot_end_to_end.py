"""End-to-end proof that the system can trade WITHOUT a per-trade human click,
while every safety gate (armed policy + Risk Engine veto) still holds.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from tradingsys.autopilot.controller import AutopilotController
from tradingsys.domain.types import (
    AccountState,
    AuthorizationKind,
    AutonomousPolicy,
    AutopilotDisposition,
    Direction,
    Recommendation,
    RecommendationAction,
    Setup,
)
from tradingsys.engines.execution.paper import PaperExecutionEngine
from tradingsys.engines.journal.engine import JournalEngine
from tradingsys.engines.risk.engine import RiskEngine


def _make_system(instruments, trades, recommendations, risk_repo, account, *, armed: bool):
    risk = RiskEngine(instruments, risk_repo)
    execution = PaperExecutionEngine(account)
    journal = JournalEngine(trades, instruments)
    policy = AutonomousPolicy(
        version=1, min_score=0.6, min_confidence=0.55, max_contracts=3,
        enabled=armed, armed_by="lucas" if armed else None,
    )
    controller = AutopilotController(
        risk=risk, execution=execution, journal=journal,
        recommendations=recommendations, policy=policy,
    )
    return controller, execution


def _rec(now, *, score=0.8, confidence=0.7, action=RecommendationAction.ENTER):
    setup = Setup(
        strategy_key="orb", instrument="ES", direction=Direction.LONG,
        proposed_entry=Decimal("5000"), proposed_stop=Decimal("4996"),
        proposed_target=Decimal("5012"), rationale="ORB long", detected_at=now,
        reward_risk=3.0, id=1,
    )
    return Recommendation(
        action=action, account_id=1, created_at=now, setup=setup,
        direction=Direction.LONG, score=score, confidence=confidence,
        entry=Decimal("5000"), stop=Decimal("4996"), target=Decimal("5012"),
        id=1,
    )


def test_autonomous_trade_executes_without_human_click(
    instruments, trades, recommendations, risk_repo, flat_account, now
):
    controller, execution = _make_system(
        instruments, trades, recommendations, risk_repo, flat_account, armed=True
    )
    outcome = controller.handle(_rec(now))

    assert outcome.disposition is AutopilotDisposition.EXECUTED
    assert outcome.trade is not None
    assert outcome.trade.id is not None                 # journaled
    assert outcome.trade.quantity == 1                  # risk-sized
    # The trade was authorized autonomously — not by a faked human click.
    assert "auth:autonomous" in outcome.trade.tags
    # Paper account reflects the new position.
    assert execution.account_state(1).open_positions == 1


def test_disarmed_policy_never_trades(
    instruments, trades, recommendations, risk_repo, flat_account, now
):
    controller, _ = _make_system(
        instruments, trades, recommendations, risk_repo, flat_account, armed=False
    )
    outcome = controller.handle(_rec(now))
    assert outcome.disposition is AutopilotDisposition.SKIPPED_DISARMED
    assert outcome.trade is None


def test_kill_switch_stops_trading(
    instruments, trades, recommendations, risk_repo, flat_account, now
):
    controller, _ = _make_system(
        instruments, trades, recommendations, risk_repo, flat_account, armed=True
    )
    controller.disarm(by="lucas", reason="stepping away")
    outcome = controller.handle(_rec(now))
    assert outcome.disposition is AutopilotDisposition.SKIPPED_DISARMED


def test_weak_evidence_skipped_by_policy(
    instruments, trades, recommendations, risk_repo, flat_account, now
):
    controller, _ = _make_system(
        instruments, trades, recommendations, risk_repo, flat_account, armed=True
    )
    outcome = controller.handle(_rec(now, score=0.3))   # below min_score
    assert outcome.disposition is AutopilotDisposition.SKIPPED_POLICY


def test_risk_veto_blocks_autonomous_trade(
    instruments, trades, recommendations, risk_repo, now
):
    # account already at its daily loss limit -> risk must veto, autopilot obeys.
    blown = AccountState(
        account_id=1, balance=Decimal("50000"), open_positions=0,
        daily_pnl=Decimal("-1000"), daily_trades=0, weekly_pnl=Decimal("0"),
        current_drawdown=Decimal("0"), is_paper=True,
    )
    controller, _ = _make_system(
        instruments, trades, recommendations, risk_repo, blown, armed=True
    )
    outcome = controller.handle(_rec(now))
    assert outcome.disposition is AutopilotDisposition.VETOED_BY_RISK
    assert outcome.trade is None


def test_paper_execution_refuses_autonomous_without_armed_policy(
    instruments, trades, recommendations, risk_repo, flat_account, now
):
    # Directly attempting a submit with a malformed autonomous authorization fails.
    from tradingsys.domain.types import Authorization
    execution = PaperExecutionEngine(flat_account)
    risk = RiskEngine(instruments, risk_repo)
    rec = _rec(now)
    decision = risk.evaluate(rec.setup, flat_account)
    bad_auth = Authorization(kind=AuthorizationKind.AUTONOMOUS, actor="autopilot",
                             policy_version=None, armed_by=None)
    with pytest.raises(PermissionError):
        execution.submit(rec, decision, bad_auth)
