"""Step 2 + Step 3 tests: journal P&L math and own-data analytics."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from tradingsys.domain.types import Direction, Trade, TradeResult
from tradingsys.engines.journal.engine import JournalEngine, contract_pnl
from tradingsys.engines.statistics.engine import StatisticsEngine


def test_contract_pnl_long_and_short(es):
    # ES: tick 0.25, $12.50/tick. A 4-point move = 16 ticks = $200 per contract.
    assert contract_pnl(es, Direction.LONG, Decimal("5000"), Decimal("5004"), 1) == Decimal("200.00")
    assert contract_pnl(es, Direction.SHORT, Decimal("5000"), Decimal("5004"), 1) == Decimal("-200.00")
    # 2 contracts doubles it.
    assert contract_pnl(es, Direction.LONG, Decimal("5000"), Decimal("4998"), 2) == Decimal("-200.00")


def test_close_trade_computes_pnl_r_multiple_and_result(instruments, trades, now):
    journal = JournalEngine(trades, instruments)
    t = journal.open_trade(Trade(
        account_id=1, instrument="ES", direction=Direction.LONG, quantity=1,
        entry_time=now, entry_price=Decimal("5000"), stop_price=Decimal("4996"),
        target_price=Decimal("5008"), risk_amount=Decimal("200"), strategy_key="orb",
    ))
    assert t.result is TradeResult.OPEN
    closed = journal.close_trade(t.id, now + timedelta(minutes=20), Decimal("5008"))
    assert closed.net_pnl == Decimal("400.00")   # 8 pts = 32 ticks = $400
    assert closed.r_multiple == 2.0              # $400 / $200 risk
    assert closed.result is TradeResult.WIN


def test_statistics_from_own_journal(instruments, trades, now):
    journal = JournalEngine(trades, instruments)
    stats = StatisticsEngine(trades)

    # Two wins (+400, +200), one loss (-200) on ORB.
    specs = [
        (Decimal("5000"), Decimal("5008"), Decimal("200")),  # +400
        (Decimal("5000"), Decimal("5004"), Decimal("200")),  # +200
        (Decimal("5000"), Decimal("4996"), Decimal("200")),  # -200
    ]
    for i, (entry, exit_, risk) in enumerate(specs):
        t = journal.open_trade(Trade(
            account_id=1, instrument="ES", direction=Direction.LONG, quantity=1,
            entry_time=now + timedelta(minutes=i), entry_price=entry,
            risk_amount=risk, strategy_key="orb",
        ))
        journal.close_trade(t.id, now + timedelta(minutes=i, seconds=30), exit_)

    m = stats.overall(account_id=1)
    assert m.sample_size == 3
    assert m.win_rate == round(2 / 3, 4)
    assert m.avg_winner == Decimal("300.00")     # (400+200)/2
    assert m.avg_loser == Decimal("-200.00")
    assert m.expectancy == Decimal("133.3333")   # (400+200-200)/3
    assert m.profit_factor == 3.0                # 600 / 200
    assert m.max_drawdown == Decimal("200.00")   # dip after the loss

    by_strat = stats.by_scope(account_id=1, scope="by_strategy")
    assert len(by_strat) == 1 and by_strat[0].scope_key == "orb"
