"""Step 8 + 12 + 13: the full paper pipeline is reproducible and feeds analytics,
learning, and the psychology review through the same journal."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

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
from tradingsys.persistence.memory import (
    InMemoryInstrumentRepository,
    InMemoryNewsRepository,
    InMemoryRiskRepository,
    InMemoryTradeRepository,
)


def _run():
    es = Instrument(symbol="ES", name="ES", exchange="CME",
                    tick_size=Decimal("0.25"), tick_value=Decimal("12.50"))
    instruments = InMemoryInstrumentRepository(); instruments.upsert(es)
    trades = InMemoryTradeRepository()
    risk_repo = InMemoryRiskRepository()
    risk_repo.seed_active(1, RiskRules(
        version=1, max_daily_loss=Decimal("1000"), max_drawdown=Decimal("2000"),
        risk_per_trade_pct=Decimal("0.005"), max_daily_trades=5, max_open_positions=1,
        max_contracts=3, max_weekly_loss=Decimal("3000"), approved_by="test",
        approved_at=datetime.now(timezone.utc)))

    risk = RiskEngine(instruments, risk_repo)
    journal = JournalEngine(trades, instruments)
    learning = LearningEngine(trades, 1)
    news = NewsEngine(InMemoryNewsRepository())
    strategies = StrategyEngine()
    strategies.register(TrendPullbackStrategy())
    strategies.register(BreakoutStrategy())
    decision = DecisionFramework(risk, learning, news, min_score=0.5, min_confidence_sample=0)

    provider = SyntheticMarketDataProvider(es, seed=7, start_price=5000, drift=0.4, volatility=1.5)
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    bars = provider.get_history("ES", "5m", start, start + timedelta(days=2))

    bt = Backtester(instrument=es, analysis=MarketAnalysisEngine(), strategies=strategies,
                    decision=decision, journal=journal)
    result = bt.run("ES", "5m", bars, 1)
    return result, trades, learning, StatisticsEngine(trades), PerformanceReviewEngine(trades)


def test_pipeline_is_reproducible():
    r1, *_ = _run()
    r2, *_ = _run()
    assert r1.ending_balance == r2.ending_balance
    assert r1.trades_opened == r2.trades_opened == r1.trades_closed


def test_pipeline_produces_trades_and_analytics():
    result, trades, learning, stats, perf = _run()
    assert result.trades_opened > 0
    overall = stats.overall(1)
    assert overall.sample_size == result.trades_closed
    assert overall.win_rate is not None
    # learning confidence is bounded and its sample matches the journal
    conf = learning.update_confidence("breakout")
    assert 0.0 <= conf.value <= 1.0
    assert conf.sample_size == len(list(trades.query(1, strategy_key="breakout")))
    # performance review runs without error and returns a list
    assert isinstance(perf.review(1), list)


def test_learning_cannot_auto_change_risk_only_propose():
    _, trades, learning, *_ = _run()
    proposals = learning.review(1)
    for p in proposals:
        if p.kind == "risk_change":
            assert p.requires_human_approval is True
