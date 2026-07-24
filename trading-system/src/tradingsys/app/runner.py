"""Local runner — wires the whole system so it runs on your own computer.

Two modes:
  * advise  — read the current market and TELL you the trade (no order placed)
  * auto    — MAKE the trades autonomously (paper now; real once a broker adapter
              is connected locally), under the Topstep account rules

Runs on synthetic data until you connect a real data feed (see docs/09). Pure
standard library — nothing to install beyond Python 3.11+.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional, Sequence

from ..backtest.prop_firm import PropFirmCombineSimulator
from ..decision.framework import DecisionFramework
from ..domain.types import (
    Bar,
    Instrument,
    MarketContext,
    Recommendation,
    RiskRules,
)
from ..engines.journal.engine import JournalEngine
from ..engines.learning.engine import LearningEngine
from ..engines.market_analysis.engine import MarketAnalysisEngine
from ..engines.market_data.synthetic import SyntheticMarketDataProvider
from ..engines.news.engine import NewsEngine
from ..engines.performance.engine import PerformanceReviewEngine
from ..engines.risk.engine import RiskEngine
from ..engines.risk.prop_firm import TopstepAccount, load_profiles
from ..engines.statistics.engine import StatisticsEngine
from ..engines.strategy.engine import StrategyEngine
from ..engines.strategy.strategies.breakout import BreakoutStrategy
from ..engines.strategy.strategies.trend_pullback import TrendPullbackStrategy
from ..interfaces.market_data import MarketDataProvider
from ..persistence.memory import (
    InMemoryInstrumentRepository,
    InMemoryNewsRepository,
    InMemoryRiskRepository,
    InMemoryTradeRepository,
)

ACCOUNT_ID = 1
CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


@dataclass
class System:
    profile_key: str
    instrument: Instrument
    trades: InMemoryTradeRepository
    journal: JournalEngine
    learning: LearningEngine
    stats: StatisticsEngine
    perf: PerformanceReviewEngine
    strategies: StrategyEngine
    decision: DecisionFramework
    analysis: MarketAnalysisEngine
    account: TopstepAccount
    provider: MarketDataProvider
    bars: Sequence[Bar]


def build_system(
    *,
    profile_key: str = "topstep_50k",
    symbol: str = "ES",
    seed: int = 7,
    drift: float = 0.35,
    volatility: float = 1.6,
    days: int = 6,
    provider: Optional[MarketDataProvider] = None,
    csv_path: Optional[str] = None,
    timeframe: str = "5m",
    strategy_list: Optional[Sequence[object]] = None,
    risk_per_trade_pct: Decimal = Decimal("0.005"),
) -> System:
    """Assemble the full engine graph. Swap `provider` for a live adapter later,
    or pass ``csv_path`` to backtest on REAL historical data from a CSV file."""
    profile = load_profiles(CONFIG_DIR / "topstep.json")[profile_key]
    account = TopstepAccount(profile=profile)

    es = Instrument(symbol=symbol, name=symbol, exchange="CME",
                    tick_size=Decimal("0.25"), tick_value=Decimal("12.50"))
    instruments = InMemoryInstrumentRepository(); instruments.upsert(es)
    trades = InMemoryTradeRepository()

    risk_repo = InMemoryRiskRepository()
    risk_repo.seed_active(ACCOUNT_ID, RiskRules(
        version=1, max_daily_loss=profile.daily_loss_limit,
        max_drawdown=profile.max_loss_limit, risk_per_trade_pct=risk_per_trade_pct,
        max_daily_trades=100, max_open_positions=1, max_contracts=profile.max_contracts,
        approved_by="local", approved_at=datetime.now(timezone.utc),
    ))

    risk = RiskEngine(instruments, risk_repo)
    journal = JournalEngine(trades, instruments)
    learning = LearningEngine(trades, ACCOUNT_ID)
    stats = StatisticsEngine(trades)
    perf = PerformanceReviewEngine(trades)
    news = NewsEngine(InMemoryNewsRepository())
    strategies = StrategyEngine()
    for strat in (strategy_list if strategy_list is not None
                  else [TrendPullbackStrategy(), BreakoutStrategy()]):
        strategies.register(strat)
    decision = DecisionFramework(risk, learning, news, min_score=0.5, min_confidence_sample=0)

    if csv_path is not None:
        from ..engines.market_data.csv_provider import CsvMarketDataProvider
        provider = CsvMarketDataProvider(es, csv_path, timeframe=timeframe)
        bars = list(provider.all_bars())
    else:
        provider = provider or SyntheticMarketDataProvider(
            es, seed=seed, start_price=5000, drift=drift, volatility=volatility)
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        bars = list(provider.get_history(symbol, timeframe, start, start + timedelta(days=days)))

    return System(profile_key, es, trades, journal, learning, stats, perf,
                  strategies, decision, analysis=MarketAnalysisEngine(),
                  account=account, provider=provider, bars=bars)


def advise(sys: System, symbol: str = "ES") -> tuple[MarketContext, list[Recommendation]]:
    """Read the CURRENT market and return the recommendation(s). Places nothing."""
    window = sys.bars
    context = sys.analysis.analyze(symbol, "5m", window)
    setups = sys.strategies.generate_setups(context, window)
    account_state = sys.account.to_account_state(ACCOUNT_ID)
    recs = [sys.decision.decide(s, account_state, window[-1].ts) for s in setups]
    return context, recs


def run_auto(
    sys: System,
    symbol: str = "ES",
    *,
    commission_per_contract: Decimal = Decimal("0"),
    slippage_ticks: int = 0,
) -> dict:
    """MAKE the trades autonomously under the account rules (paper). Returns the
    Combine status after the session. Pass costs for a realistic run."""
    sim = PropFirmCombineSimulator(
        instrument=sys.instrument, analysis=sys.analysis, strategies=sys.strategies,
        decision=sys.decision, journal=sys.journal, account=sys.account,
        commission_per_contract=commission_per_contract, slippage_ticks=slippage_ticks,
    )
    return sim.run(symbol, "5m", sys.bars, ACCOUNT_ID)
