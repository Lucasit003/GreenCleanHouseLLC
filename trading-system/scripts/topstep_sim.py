"""Simulate a Topstep Trading Combine with fake trades under the real rules.

    python scripts/topstep_sim.py            # default: 50K profile
    python scripts/topstep_sim.py topstep_100k 123   # profile + seed

It runs the full decision pipeline through a TopstepAccount that enforces the
trailing max loss, daily loss limit, contract cap, profit target, and minimum
trading days — halting the moment the Combine is PASSED or FAILED — then prints a
status report as if you were sitting in the evaluation.

⚠️  All simulated. No account, no orders. VERIFY the rule numbers in
config/topstep.json against Topstep's current site before drawing conclusions.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tradingsys.backtest.prop_firm import PropFirmCombineSimulator
from tradingsys.decision.framework import DecisionFramework
from tradingsys.domain.types import Instrument, RiskRules
from tradingsys.engines.journal.engine import JournalEngine
from tradingsys.engines.learning.engine import LearningEngine
from tradingsys.engines.market_analysis.engine import MarketAnalysisEngine
from tradingsys.engines.market_data.synthetic import SyntheticMarketDataProvider
from tradingsys.engines.news.engine import NewsEngine
from tradingsys.engines.risk.engine import RiskEngine
from tradingsys.engines.risk.prop_firm import TopstepAccount, load_profiles
from tradingsys.engines.strategy.engine import StrategyEngine
from tradingsys.engines.strategy.strategies.breakout import BreakoutStrategy
from tradingsys.engines.strategy.strategies.trend_pullback import TrendPullbackStrategy
from tradingsys.persistence.memory import (
    InMemoryInstrumentRepository,
    InMemoryNewsRepository,
    InMemoryRiskRepository,
    InMemoryTradeRepository,
)

ACCOUNT_ID = 1


def main() -> None:
    profile_key = sys.argv[1] if len(sys.argv) > 1 else "topstep_50k"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    profiles = load_profiles(ROOT / "config" / "topstep.json")
    profile = profiles[profile_key]
    account = TopstepAccount(profile=profile)

    es = Instrument(symbol="ES", name="E-mini S&P 500", exchange="CME",
                    tick_size=Decimal("0.25"), tick_value=Decimal("12.50"))
    instruments = InMemoryInstrumentRepository(); instruments.upsert(es)
    trades = InMemoryTradeRepository()

    # The generic Risk Engine is configured FROM the prop-firm profile, so the
    # same veto that guards live trading also enforces the Combine here.
    risk_repo = InMemoryRiskRepository()
    risk_repo.seed_active(ACCOUNT_ID, RiskRules(
        version=1, max_daily_loss=profile.daily_loss_limit,
        max_drawdown=profile.max_loss_limit, risk_per_trade_pct=Decimal("0.005"),
        max_daily_trades=100, max_open_positions=1, max_contracts=profile.max_contracts,
        approved_by="practice", approved_at=datetime.now(timezone.utc),
    ))

    risk = RiskEngine(instruments, risk_repo)
    journal = JournalEngine(trades, instruments)
    learning = LearningEngine(trades, ACCOUNT_ID)
    news = NewsEngine(InMemoryNewsRepository())
    strategies = StrategyEngine()
    strategies.register(TrendPullbackStrategy())
    strategies.register(BreakoutStrategy())
    decision = DecisionFramework(risk, learning, news, min_score=0.5, min_confidence_sample=0)

    provider = SyntheticMarketDataProvider(es, seed=seed, start_price=5000, drift=0.35, volatility=1.6)
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    bars = provider.get_history("ES", "5m", start, start + timedelta(days=6))

    sim = PropFirmCombineSimulator(
        instrument=es, analysis=MarketAnalysisEngine(), strategies=strategies,
        decision=decision, journal=journal, account=account,
    )
    status = sim.run("ES", "5m", bars, ACCOUNT_ID)

    print(f"=== {status['profile']} — Combine simulation (seed={seed}) ===\n")
    verdict = {"passed": "✅ PASSED", "failed": "❌ FAILED", "active": "… still ACTIVE (ran out of data)"}
    print(f"Result: {verdict.get(status['state'], status['state'])}")
    if status["fail_reason"]:
        print(f"Reason: {status['fail_reason']}")
    print()
    print(f"Equity:              ${status['equity']}")
    print(f"Realized P&L:        ${status['realized_pnl']}  (target ${status['profit_target']}, "
          f"{status['profit_progress_pct']}%)")
    print(f"Trailing max-loss @:  ${status['trailing_threshold']}   (room left: ${status['max_loss_room']})")
    print(f"Daily-loss room:      ${status['daily_loss_room']}")
    print(f"Trading days:         {status['trading_days']} / {status['min_trading_days']} required")
    print(f"Consistency rule ok:  {status['consistency_ok']}")
    print()
    print(f"Trades — opened: {status['opened']}, closed: {status['closed']}, "
          f"blocked by rules: {status['blocked_by_rules']}")
    print("\n(simulation only — verify rule numbers in config/topstep.json against Topstep)")


if __name__ == "__main__":
    main()
