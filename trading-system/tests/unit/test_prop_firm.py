"""Topstep Combine rule model — pass, trailing lock, MLL fail, DLL lockout."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from tradingsys.domain.types import Direction, Trade, TradeResult
from tradingsys.engines.risk.prop_firm import (
    ComboState,
    PropFirmProfile,
    TopstepAccount,
    load_profiles,
)

DAY0 = datetime(2026, 7, 1, 14, 0, tzinfo=timezone.utc)


def _profile(**over) -> PropFirmProfile:
    base = dict(
        name="Test 50K", account_size=Decimal("50000"), profit_target=Decimal("3000"),
        max_loss_limit=Decimal("2000"), daily_loss_limit=Decimal("1000"),
        max_contracts=5, min_trading_days=2, trailing_locks_at_starting_balance=True,
        on_daily_loss="lockout", consistency_pct=None,
    )
    base.update(over)
    return PropFirmProfile(**base)


def _trade(pnl, when, qty=1) -> Trade:
    t = Trade(account_id=1, instrument="ES", direction=Direction.LONG, quantity=qty,
              entry_time=when, entry_price=Decimal("5000"), exit_time=when + timedelta(minutes=5))
    t.net_pnl = Decimal(str(pnl))
    t.result = TradeResult.WIN if pnl > 0 else TradeResult.LOSS
    return t


def test_config_file_loads():
    profiles = load_profiles(Path(__file__).resolve().parents[2] / "config" / "topstep.json")
    assert "topstep_50k" in profiles
    assert profiles["topstep_50k"].account_size == Decimal("50000")


def test_pass_requires_target_and_min_days():
    acct = TopstepAccount(profile=_profile())
    # +2000 on day 1 (not enough days yet even though close to target)
    acct.record_trade(_trade(2000, DAY0))
    assert acct.state is ComboState.ACTIVE
    # +1500 on day 2 -> total 3500 >= 3000 and 2 trading days -> PASSED
    acct.record_trade(_trade(1500, DAY0 + timedelta(days=1)))
    assert acct.state is ComboState.PASSED


def test_trailing_threshold_locks_at_starting_balance():
    acct = TopstepAccount(profile=_profile())
    # threshold starts at 50000 - 2000 = 48000
    assert acct.trailing_threshold == Decimal("48000")
    # after +$5000, peak=55000, raw threshold=53000 but LOCKS at 50000
    acct.record_trade(_trade(5000, DAY0))
    assert acct.trailing_threshold == Decimal("50000")


def test_trailing_max_loss_failure():
    acct = TopstepAccount(profile=_profile(daily_loss_limit=Decimal("5000")))  # avoid daily trip
    # lose 2000 in one shot from the start -> equity 48000 <= threshold 48000 -> FAIL
    acct.record_trade(_trade(-2000, DAY0))
    assert acct.state is ComboState.FAILED
    assert "trailing max loss" in (acct.fail_reason or "")


def test_daily_loss_lockout_then_can_trade_false():
    acct = TopstepAccount(profile=_profile())
    acct.record_trade(_trade(-1000, DAY0))    # hits daily loss limit exactly
    assert acct.locked_today is True
    assert acct.state is ComboState.ACTIVE     # lockout, not failed
    ok, reasons = acct.can_trade(contracts=1, projected_loss=Decimal("200"))
    assert ok is False
    assert any("locked out" in r for r in reasons)


def test_can_trade_blocks_projected_daily_breach():
    acct = TopstepAccount(profile=_profile())
    acct.record_trade(_trade(-800, DAY0))      # $200 of daily room left
    ok, reasons = acct.can_trade(contracts=1, projected_loss=Decimal("300"))
    assert ok is False
    assert any("daily loss limit" in r for r in reasons)


def test_can_trade_blocks_contract_cap():
    acct = TopstepAccount(profile=_profile())
    ok, reasons = acct.can_trade(contracts=6, projected_loss=Decimal("100"))
    assert ok is False
    assert any("exceeds max" in r for r in reasons)


def test_risk_engine_adapter_maps_drawdown():
    acct = TopstepAccount(profile=_profile(daily_loss_limit=Decimal("5000")))
    acct.record_trade(_trade(-1500, DAY0))     # equity 48500, threshold 48000
    st = acct.to_account_state(account_id=1)
    # current_drawdown vs max_loss_limit(2000): 1500 used, not yet a breach
    assert st.current_drawdown == Decimal("1500")
    assert st.balance == Decimal("48500")
