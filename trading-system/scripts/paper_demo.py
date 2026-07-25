"""End-to-end PAPER practice run — wires every engine together, no external infra.

    python scripts/paper_demo.py

What it does (all simulated, no account, no orders leave the process):
  1. generates deterministic synthetic ES bars (trending regime),
  2. runs the full pipeline via the Backtester: analysis -> strategy -> decision
     (risk-gated) -> journal, simulating fills,
  3. updates strategy confidence from the resulting own-data,
  4. runs the performance-review (psychology) checks,
  5. prints the Dashboard v1 report.

Change `drift`/`volatility`/`seed` below to practice different market regimes.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingsys.backtest.harness import Backtester
from tradingsys.decision.framework import DecisionFramework
from tradingsys.domain.types import Instrument, RiskRules
from tradingsys.engines.journal.engine import JournalEngine
from tradingsys.engines.learning.engine import LearningEngine
from tradingsys.engines.market_analysis.engine import MarketAnalysisEngine
from tradingsys.engines.market_data.synthetic import SyntheticMarketDataProvider
from tradingsys.engines.news.engine import NewsEngine
from tradingsys.engines.performance.engine import PerformanceReviewEngine
from tradingsys.engines.risk.engine import RiskEngine
from tradingsys.engines.statistics.engine import StatisticsEngine
from tradingsys.engines.strategy.engine import StrategyEngine
from tradingsys.engines.strategy.strategies.breakout import BreakoutStrategy
from tradingsys.engines.strategy.strategies.trend_pullback import TrendPullbackStrategy
from tradingsys.dashboard.report import render_report
from tradingsys.persistence.memory import (
    InMemoryInstrumentRepository,
    InMemoryNewsRepository,
    InMemoryRiskRepository,
    InMemoryTradeRepository,
)

ACCOUNT_ID = 1


def build_system():
    es = Instrument(symbol="ES", name="E-mini S&P 500", exchange="CME",
                    tick_size=Decimal("0.25"), tick_value=Decimal("12.50"))
    instruments = InMemoryInstrumentRepository()
    instruments.upsert(es)

    trades = InMemoryTradeRepository()
    risk_repo = InMemoryRiskRepository()
    risk_repo.seed_active(ACCOUNT_ID, RiskRules(
        version=1, max_daily_loss=Decimal("1000"), max_drawdown=Decimal("2000"),
        risk_per_trade_pct=Decimal("0.005"), max_daily_trades=5,
        max_open_positions=1, max_contracts=3, max_weekly_loss=Decimal("3000"),
        approved_by="practice", approved_at=datetime.now(timezone.utc),
    ))
    news = NewsEngine(InMemoryNewsRepository())

    risk = RiskEngine(instruments, risk_repo)
    journal = JournalEngine(trades, instruments)
    learning = LearningEngine(trades, ACCOUNT_ID)
    stats = StatisticsEngine(trades)
    perf = PerformanceReviewEngine(trades, max_trades_per_day=5)

    strategies = StrategyEngine()
    strategies.register(TrendPullbackStrategy())
    strategies.register(BreakoutStrategy())

    decision = DecisionFramework(risk, learning, news, min_score=0.5, min_confidence_sample=0)
    analysis = MarketAnalysisEngine()
    return es, trades, journal, learning, stats, perf, strategies, decision, analysis


def main() -> None:
    es, trades, journal, learning, stats, perf, strategies, decision, analysis = build_system()

    provider = SyntheticMarketDataProvider(es, seed=7, start_price=5000, drift=0.4, volatility=1.5)
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=2)
    bars = provider.get_history("ES", "5m", start, end)

    backtester = Backtester(
        instrument=es, analysis=analysis, strategies=strategies,
        decision=decision, journal=journal, starting_balance=Decimal("50000"),
    )
    result = backtester.run("ES", "5m", bars, ACCOUNT_ID)

    confidences = [learning.update_confidence(s.key) for s in strategies.enabled_strategies()]
    report = render_report(
        overall=stats.overall(ACCOUNT_ID),
        by_strategy=stats.by_scope(ACCOUNT_ID, "by_strategy"),
        confidences=confidences,
        flags=perf.review(ACCOUNT_ID),
        recent_trades=list(trades.query(ACCOUNT_ID)),
    )
    print(report)
    print(f"\nBars simulated: {len(bars)} | opened: {result.trades_opened} "
          f"| closed: {result.trades_closed} | ending balance: {result.ending_balance}")
    print("\n(paper simulation only — no account, no live orders)")


if __name__ == "__main__":
    main()
