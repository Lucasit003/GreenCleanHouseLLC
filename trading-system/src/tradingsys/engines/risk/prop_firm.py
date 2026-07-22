"""Prop-firm (Topstep) Combine account model.

Models the rules of a Topstep Trading Combine so trades can be simulated exactly
as if you were in a funded-account evaluation:

  * TRAILING maximum loss limit (the distinctive Topstep mechanic),
  * daily loss limit (lockout or fail),
  * profit target + minimum trading days to pass,
  * per-account contract cap,
  * optional consistency rule.

⚠️  Rules change and vary by program/account size. The numbers come from
``config/topstep.json`` which you must verify against Topstep's current site.
The trailing limit here trails on REALIZED (closed-trade) equity, which is
slightly more lenient than Topstep's intraday-including-open-profit trail — so a
pass here is necessary, not sufficient. See docs/08.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Optional

from ...domain.types import AccountState, Trade


@dataclass(frozen=True)
class PropFirmProfile:
    name: str
    account_size: Decimal
    profit_target: Decimal
    max_loss_limit: Decimal          # trailing
    daily_loss_limit: Decimal
    max_contracts: int
    min_trading_days: int
    trailing_locks_at_starting_balance: bool = True
    on_daily_loss: str = "lockout"   # 'lockout' | 'fail'
    consistency_pct: Optional[float] = None


def load_profiles(path: str | Path) -> dict[str, PropFirmProfile]:
    data = json.loads(Path(path).read_text())
    out: dict[str, PropFirmProfile] = {}
    for key, p in data.get("profiles", {}).items():
        out[key] = PropFirmProfile(
            name=p["name"],
            account_size=Decimal(str(p["account_size"])),
            profit_target=Decimal(str(p["profit_target"])),
            max_loss_limit=Decimal(str(p["max_loss_limit"])),
            daily_loss_limit=Decimal(str(p["daily_loss_limit"])),
            max_contracts=int(p["max_contracts"]),
            min_trading_days=int(p["min_trading_days"]),
            trailing_locks_at_starting_balance=bool(p.get("trailing_locks_at_starting_balance", True)),
            on_daily_loss=str(p.get("on_daily_loss", "lockout")),
            consistency_pct=(None if p.get("consistency_pct") is None else float(p["consistency_pct"])),
        )
    return out


class ComboState(str, Enum):
    ACTIVE = "active"
    PASSED = "passed"
    FAILED = "failed"


@dataclass
class TopstepAccount:
    """A live-updating Combine account. Feed it closed trades in time order."""
    profile: PropFirmProfile
    realized: Decimal = Decimal("0")
    peak_equity: Decimal = field(default=Decimal("0"))
    day: Optional[date] = None
    daily_pnl: Decimal = Decimal("0")
    daily_trades: int = 0
    locked_today: bool = False
    state: ComboState = ComboState.ACTIVE
    fail_reason: Optional[str] = None
    trading_days: set = field(default_factory=set)
    daily_profits: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.peak_equity == 0:
            self.peak_equity = self.profile.account_size

    # --- derived numbers ------------------------------------------------
    @property
    def equity(self) -> Decimal:
        return self.profile.account_size + self.realized

    @property
    def trailing_threshold(self) -> Decimal:
        """The equity level that, if breached, fails the account."""
        raw = self.peak_equity - self.profile.max_loss_limit
        if self.profile.trailing_locks_at_starting_balance:
            return min(raw, self.profile.account_size)
        return raw

    @property
    def mll_room(self) -> Decimal:
        """How much more you can lose before the trailing max loss fails you."""
        return self.equity - self.trailing_threshold

    @property
    def dll_room(self) -> Decimal:
        """How much more you can lose today before the daily limit."""
        return self.profile.daily_loss_limit + self.daily_pnl  # daily_pnl<=0 shrinks it

    @property
    def profit_progress(self) -> float:
        if self.profile.profit_target <= 0:
            return 1.0
        return float(self.realized / self.profile.profit_target)

    @property
    def consistency_ok(self) -> bool:
        if self.profile.consistency_pct is None or self.realized <= 0:
            return True
        best_day = max(self.daily_profits.values(), default=Decimal("0"))
        return best_day <= Decimal(str(self.profile.consistency_pct)) * self.realized

    # --- day handling ----------------------------------------------------
    def _roll_day(self, d: date) -> None:
        if d != self.day:
            self.day = d
            self.daily_pnl = Decimal("0")
            self.daily_trades = 0
            self.locked_today = False

    # --- pre-trade gate --------------------------------------------------
    def can_trade(self, contracts: int, projected_loss: Decimal) -> tuple[bool, list[str]]:
        """Would this order be permitted right now? projected_loss is the $ lost
        if the stop is hit (a positive number)."""
        reasons: list[str] = []
        if self.state is not ComboState.ACTIVE:
            reasons.append(f"combine is {self.state.value}")
        if self.locked_today:
            reasons.append("locked out for the day (daily loss limit hit)")
        if contracts < 1:
            reasons.append("size below 1 contract")
        if contracts > self.profile.max_contracts:
            reasons.append(f"{contracts} contracts exceeds max {self.profile.max_contracts}")
        if self.daily_pnl - projected_loss <= -self.profile.daily_loss_limit:
            reasons.append("would breach the daily loss limit if stopped out")
        if self.equity - projected_loss <= self.trailing_threshold:
            reasons.append("would breach the trailing max loss if stopped out")
        return (len(reasons) == 0, reasons)

    # --- record a closed trade ------------------------------------------
    def record_trade(self, trade: Trade) -> None:
        if self.state is not ComboState.ACTIVE or trade.net_pnl is None:
            return
        d = (trade.exit_time or trade.entry_time).date()
        self._roll_day(d)

        pnl = trade.net_pnl
        self.realized += pnl
        self.daily_pnl += pnl
        self.daily_trades += 1
        self.trading_days.add(d)
        self.daily_profits[d] = self.daily_profits.get(d, Decimal("0")) + pnl

        # peak only ratchets up (trailing drawdown basis)
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

        # --- failure checks (hard) ---
        if self.equity <= self.trailing_threshold:
            self.state = ComboState.FAILED
            self.fail_reason = "trailing max loss limit breached"
            return
        if self.daily_pnl <= -self.profile.daily_loss_limit:
            if self.profile.on_daily_loss == "fail":
                self.state = ComboState.FAILED
                self.fail_reason = "daily loss limit breached"
                return
            self.locked_today = True  # lockout mode: done for the day, not failed

        # --- pass check ---
        if (
            self.realized >= self.profile.profit_target
            and len(self.trading_days) >= self.profile.min_trading_days
            and self.consistency_ok
        ):
            self.state = ComboState.PASSED

    # --- adapters --------------------------------------------------------
    def to_account_state(self, account_id: int, open_positions: int = 0) -> AccountState:
        """Feed the generic Risk Engine so the SAME veto guards the sim.

        current_drawdown maps so that (current_drawdown >= max_loss_limit) is
        exactly (equity <= trailing_threshold), across the trailing-and-locked
        phases.
        """
        capped_peak = min(self.peak_equity, self.profile.account_size + self.profile.max_loss_limit) \
            if self.profile.trailing_locks_at_starting_balance else self.peak_equity
        return AccountState(
            account_id=account_id,
            balance=self.equity,
            open_positions=open_positions,
            daily_pnl=self.daily_pnl,
            daily_trades=self.daily_trades,
            weekly_pnl=self.realized,
            current_drawdown=capped_peak - self.equity,
            is_paper=True,
        )

    def status(self) -> dict:
        return {
            "profile": self.profile.name,
            "state": self.state.value,
            "fail_reason": self.fail_reason,
            "equity": self.equity,
            "realized_pnl": self.realized,
            "profit_target": self.profile.profit_target,
            "profit_progress_pct": round(self.profit_progress * 100, 1),
            "trailing_threshold": self.trailing_threshold,
            "max_loss_room": self.mll_room,
            "daily_loss_room": self.dll_room,
            "trading_days": len(self.trading_days),
            "min_trading_days": self.profile.min_trading_days,
            "locked_today": self.locked_today,
            "consistency_ok": self.consistency_ok,
        }
