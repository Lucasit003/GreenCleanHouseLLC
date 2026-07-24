"""Journal Engine implementation (Step 2).

Records every trade and, at close, computes futures P&L exactly (Decimal),
derives the R-multiple and win/loss result, and persists them for fast
own-data analytics. Depends only on repository + instrument Protocols.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from ...domain.types import Direction, Instrument, Trade, TradeResult
from ...interfaces.repository import InstrumentRepository, TradeRepository


def contract_pnl(
    instrument: Instrument, direction: Direction, entry: Decimal, exit_: Decimal, qty: int
) -> Decimal:
    """Gross P&L in account currency for a futures position.

    dollars = (price move in ticks) * tick_value * quantity
    """
    ticks = (exit_ - entry) / instrument.tick_size
    if direction is Direction.SHORT:
        ticks = -ticks
    return (ticks * instrument.tick_value * Decimal(qty)).quantize(Decimal("0.01"))


class JournalEngine:
    def __init__(self, trades: TradeRepository, instruments: InstrumentRepository) -> None:
        self._trades = trades
        self._instruments = instruments

    def open_trade(self, trade: Trade) -> Trade:
        trade.result = TradeResult.OPEN
        return self._trades.add(trade)

    def close_trade(
        self,
        trade_id: int,
        exit_time: datetime,
        exit_price: Decimal,
        exit_reason: Optional[str] = None,
        fees: Decimal = Decimal("0"),
    ) -> Trade:
        trade = self._trades.get(trade_id)
        if trade is None:
            raise KeyError(f"trade {trade_id} not found")
        instrument = self._instruments.get(trade.instrument)
        if instrument is None:
            raise KeyError(f"instrument {trade.instrument} not found")

        gross = contract_pnl(instrument, trade.direction, trade.entry_price, exit_price, trade.quantity)
        trade.fees = fees
        net = gross - fees

        trade.exit_time = exit_time
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.net_pnl = net
        if trade.risk_amount and trade.risk_amount > 0:
            trade.r_multiple = float(net / trade.risk_amount)
        if net > 0:
            trade.result = TradeResult.WIN
        elif net < 0:
            trade.result = TradeResult.LOSS
        else:
            trade.result = TradeResult.BREAKEVEN
        return self._trades.update(trade)

    def annotate(
        self,
        trade_id: int,
        *,
        mistakes: Optional[str] = None,
        lessons: Optional[str] = None,
        screenshot_url: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> Trade:
        trade = self._trades.get(trade_id)
        if trade is None:
            raise KeyError(f"trade {trade_id} not found")
        if mistakes is not None:
            trade.mistakes = mistakes
        if lessons is not None:
            trade.lessons = lessons
        if screenshot_url is not None:
            trade.screenshot_url = screenshot_url
        if tags is not None:
            trade.tags = list(tags)
        return self._trades.update(trade)

    def get(self, trade_id: int) -> Optional[Trade]:
        return self._trades.get(trade_id)

    def history(
        self,
        account_id: int,
        *,
        strategy_key: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Sequence[Trade]:
        return self._trades.query(
            account_id, strategy_key=strategy_key, start=start, end=end
        )
