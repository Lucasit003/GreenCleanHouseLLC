"""Prop-firm Combine simulator.

Runs the real decision pipeline (analysis → strategy → decision → risk) trade by
trade through a ``TopstepAccount``, enforcing the prop-firm rules exactly as the
evaluation would: contract cap, daily loss lockout, and the trailing max loss.
It halts the moment the Combine is PASSED or FAILED and returns the full status.

This is "make fake trades as if you were in that position" — no account, no live
orders, just the rules applied to simulated fills.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Sequence

from ..decision.framework import DecisionFramework
from ..domain.types import Bar, Instrument, RecommendationAction, Trade
from ..engines.journal.engine import JournalEngine
from ..engines.market_analysis.engine import MarketAnalysisEngine
from ..engines.risk.prop_firm import ComboState, TopstepAccount
from ..engines.strategy.engine import StrategyEngine


class PropFirmCombineSimulator:
    def __init__(
        self,
        *,
        instrument: Instrument,
        analysis: MarketAnalysisEngine,
        strategies: StrategyEngine,
        decision: DecisionFramework,
        journal: JournalEngine,
        account: TopstepAccount,
        warmup: int = 30,
        commission_per_contract: Decimal = Decimal("0"),  # round-turn $ per contract
        slippage_ticks: int = 0,                          # applied each side
        scale_size_near_limit: bool = False,              # trade smaller vs. refuse
    ) -> None:
        self._instrument = instrument
        self._analysis = analysis
        self._strategies = strategies
        self._decision = decision
        self._journal = journal
        self._account = account
        self._warmup = warmup
        self._commission = commission_per_contract
        self._slip = instrument.tick_size * Decimal(slippage_ticks)
        self._scale = scale_size_near_limit

    def _per_contract_risk(self, entry: Decimal, stop: Decimal) -> Decimal:
        return abs(entry - stop) / self._instrument.tick_size * self._instrument.tick_value

    def run(self, symbol: str, timeframe: str, bars: Sequence[Bar], account_id: int = 1) -> dict:
        position: Optional[dict] = None
        opened = closed = blocked = 0

        for i in range(self._warmup, len(bars)):
            if self._account.state is not ComboState.ACTIVE:
                break
            bar = bars[i]
            # roll the account's calendar day as time passes so the daily loss
            # limit / lockout reset each day (not only when a trade closes)
            self._account.sync_day(bar.ts.date())

            # --- manage an open position (stop checked before target) ---
            if position is not None:
                exit_price = None
                if position["dir"] == "long":
                    if bar.low <= position["stop"]:
                        exit_price = position["stop"]
                    elif bar.high >= position["target"]:
                        exit_price = position["target"]
                else:
                    if bar.high >= position["stop"]:
                        exit_price = position["stop"]
                    elif bar.low <= position["target"]:
                        exit_price = position["target"]
                if exit_price is not None:
                    # exit fill slips against you; commission charged round-turn
                    fill = exit_price - self._slip if position["dir"] == "long" else exit_price + self._slip
                    fees = self._commission * Decimal(position["size"])
                    t = self._journal.close_trade(position["trade_id"], bar.ts, fill, fees=fees)
                    self._account.record_trade(t)
                    closed += 1
                    position = None
                continue

            # --- flat: evaluate a new entry through the full pipeline ---
            # fixed lookback (indicators only need recent bars) — correct AND
            # keeps the run O(n) so month-long windows are feasible.
            window = bars[max(0, i + 1 - 250): i + 1]
            context = self._analysis.analyze(symbol, timeframe, window)
            setups = self._strategies.generate_setups(context, window)
            if not setups:
                continue

            account_state = self._account.to_account_state(account_id, open_positions=0)
            rec = self._decision.decide(setups[0], account_state, bar.ts)
            if rec.action is not RecommendationAction.ENTER or not rec.suggested_size:
                continue

            entry = rec.entry or setups[0].proposed_entry
            stop = rec.stop or setups[0].proposed_stop
            target = rec.target or setups[0].proposed_target
            size = rec.suggested_size

            # --- prop-firm gate: trailing MLL, daily lockout, contract cap ---
            per_c = self._per_contract_risk(entry, stop)
            if self._scale and per_c > 0:
                # trade SMALLER near the limit instead of refusing, so the
                # account resolves (pass/fail) rather than sitting pinned.
                room = min(self._account.mll_room, self._account.dll_room)
                by_room = int(room / per_c) if room > 0 else 0
                size = max(1, min(size, by_room)) if by_room >= 1 else 1
                a = self._account
                allowed = (a.state.value == "active" and not a.locked_today
                           and 1 <= size <= a.profile.max_contracts)
                reasons = () if allowed else ("state/lockout/cap",)
            else:
                projected_loss = per_c * Decimal(size)
                allowed, reasons = self._account.can_trade(size, projected_loss)
            if not allowed:
                blocked += 1
                continue

            risk_amount = self._per_contract_risk(entry, stop) * Decimal(size)
            # entry fill slips against you
            fill_entry = entry + self._slip if rec.direction.value == "long" else entry - self._slip
            trade = self._journal.open_trade(Trade(
                account_id=account_id, instrument=symbol, direction=rec.direction,
                quantity=size, entry_time=bar.ts, entry_price=fill_entry, is_paper=True,
                stop_price=stop, target_price=target, strategy_key=setups[0].strategy_key,
                risk_amount=risk_amount, session=context.session, entry_reason=setups[0].rationale,
            ))
            position = {"trade_id": trade.id, "dir": rec.direction.value, "stop": stop,
                        "target": target, "size": size}
            opened += 1

        return {
            "opened": opened,
            "closed": closed,
            "blocked_by_rules": blocked,
            **self._account.status(),
        }
