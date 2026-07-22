"""Backtesting harness (Step 8).

Replays bars through the SAME pipeline the live system uses — analysis →
strategy → decision (risk-gated) → journal — and simulates fills. Because it
writes through the same Journal schema, its output feeds the Statistics and
Learning engines unchanged. Deterministic: same bars + seed → same results.

This is the core "practice" tool: run it on synthetic trending/ranging data (or
real CSV history later) and study how the strategies and risk controls behave
before any account exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Sequence

from ..domain.types import AccountState, Bar, Direction, Instrument, Trade
from ..decision.framework import DecisionFramework
from ..domain.types import RecommendationAction
from ..engines.journal.engine import JournalEngine
from ..engines.market_analysis.engine import MarketAnalysisEngine
from ..engines.strategy.engine import StrategyEngine


@dataclass
class BacktestResult:
    trades_opened: int
    trades_closed: int
    ending_balance: Decimal
    trade_ids: list[int]


class Backtester:
    def __init__(
        self,
        *,
        instrument: Instrument,
        analysis: MarketAnalysisEngine,
        strategies: StrategyEngine,
        decision: DecisionFramework,
        journal: JournalEngine,
        starting_balance: Decimal = Decimal("50000"),
        warmup: int = 30,
    ) -> None:
        self._instrument = instrument
        self._analysis = analysis
        self._strategies = strategies
        self._decision = decision
        self._journal = journal
        self._start_balance = starting_balance
        self._warmup = warmup

    def _per_contract_risk(self, entry: Decimal, stop: Decimal) -> Decimal:
        ticks = abs(entry - stop) / self._instrument.tick_size
        return ticks * self._instrument.tick_value

    def run(self, symbol: str, timeframe: str, bars: Sequence[Bar], account_id: int = 1) -> BacktestResult:
        realized = Decimal("0")
        peak = Decimal("0")
        max_dd = Decimal("0")
        cur_day = None
        daily_pnl = Decimal("0")
        daily_trades = 0
        position: Optional[dict] = None
        opened = 0
        closed = 0
        trade_ids: list[int] = []

        for i in range(self._warmup, len(bars)):
            bar = bars[i]
            # reset daily counters on day change
            if bar.ts.date() != cur_day:
                cur_day = bar.ts.date()
                daily_pnl = Decimal("0")
                daily_trades = 0

            # --- manage an open position: check stop then target (conservative) ---
            if position is not None:
                exit_price = None
                if position["direction"] is Direction.LONG:
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
                    t = self._journal.close_trade(position["trade_id"], bar.ts, exit_price)
                    realized += t.net_pnl or Decimal("0")
                    daily_pnl += t.net_pnl or Decimal("0")
                    peak = max(peak, realized)
                    max_dd = max(max_dd, peak - realized)
                    closed += 1
                    position = None
                    continue  # one action per bar

            if position is not None:
                continue

            # --- flat: look for a new entry ---
            window = bars[: i + 1]
            context = self._analysis.analyze(symbol, timeframe, window)
            setups = self._strategies.generate_setups(context, window)
            if not setups:
                continue

            account = AccountState(
                account_id=account_id,
                balance=self._start_balance + realized,
                open_positions=0,
                daily_pnl=daily_pnl,
                daily_trades=daily_trades,
                weekly_pnl=realized,
                current_drawdown=max_dd,
                is_paper=True,
            )
            rec = self._decision.decide(setups[0], account, bar.ts)
            if rec.action is not RecommendationAction.ENTER or not rec.suggested_size:
                continue

            entry = rec.entry or setups[0].proposed_entry
            stop = rec.stop or setups[0].proposed_stop
            target = rec.target or setups[0].proposed_target
            size = rec.suggested_size
            risk_amount = self._per_contract_risk(entry, stop) * Decimal(size)
            trade = self._journal.open_trade(Trade(
                account_id=account_id, instrument=symbol, direction=rec.direction,
                quantity=size, entry_time=bar.ts, entry_price=entry, is_paper=True,
                stop_price=stop, target_price=target, strategy_key=setups[0].strategy_key,
                risk_amount=risk_amount, session=context.session, entry_reason=setups[0].rationale,
            ))
            trade_ids.append(trade.id)  # type: ignore[arg-type]
            position = {
                "trade_id": trade.id, "direction": rec.direction,
                "stop": stop, "target": target,
            }
            opened += 1
            daily_trades += 1

        # mark out any still-open position at the last close
        if position is not None:
            last = bars[-1]
            t = self._journal.close_trade(position["trade_id"], last.ts, last.close, "backtest_end")
            realized += t.net_pnl or Decimal("0")
            closed += 1

        return BacktestResult(
            trades_opened=opened, trades_closed=closed,
            ending_balance=self._start_balance + realized, trade_ids=trade_ids,
        )
