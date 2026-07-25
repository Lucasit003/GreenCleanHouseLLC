"""Strategy bake-off — run each strategy in isolation and rank them by evidence.

Each strategy is run ALONE through the same market scenarios and the same
Topstep rules, so their results are directly comparable. Metrics are pooled
across all runs per strategy (win rate, expectancy, profit factor, drawdown,
Sharpe) plus the Combine pass-rate.

This is exactly the project's philosophy in action: let measured evidence — not
opinion — decide which strategy is good, and beware reading too much into any
single sample (see the caveats printed by the CLI).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional, Sequence

from ..app.runner import build_system, run_auto
from ..domain.types import PerformanceMetrics, Trade
from ..engines.statistics.engine import StatisticsEngine
from ..persistence.memory import InMemoryTradeRepository

# A scenario is a label + market parameters for the synthetic generator.
DEFAULT_SCENARIOS: list[tuple[str, dict]] = [
    ("uptrend", dict(drift=0.40, volatility=1.5)),
    ("grind_up", dict(drift=0.20, volatility=0.9)),
    ("range", dict(drift=0.0, volatility=1.6)),
    ("downtrend", dict(drift=-0.40, volatility=1.5)),
    ("high_vol", dict(drift=0.10, volatility=3.2)),
]


@dataclass
class StrategyScore:
    key: str
    runs: int
    combine_pass_rate: float
    avg_pnl: Decimal
    metrics: PerformanceMetrics  # pooled across all runs


def run_tournament(
    strategy_factories: dict[str, Callable[[], object]],
    *,
    seeds: Sequence[int] = (7, 21, 34),
    scenarios: Optional[list[tuple[str, dict]]] = None,
    profile_key: str = "topstep_50k",
    days: int = 6,
) -> list[StrategyScore]:
    scenarios = scenarios or DEFAULT_SCENARIOS
    scores: list[StrategyScore] = []

    for key, factory in strategy_factories.items():
        pooled = InMemoryTradeRepository()
        runs = 0
        passes = 0
        pnls: list[Decimal] = []

        for _, params in scenarios:
            for seed in seeds:
                system = build_system(
                    profile_key=profile_key, seed=seed, days=days,
                    strategy_list=[factory()], **params,
                )
                status = run_auto(system)
                runs += 1
                if status["state"] == "passed":
                    passes += 1
                pnls.append(Decimal(str(status["realized_pnl"])))
                # pool this run's trades (reset ids to avoid collisions)
                for t in system.trades.query(1):
                    pooled.add(Trade(**{**t.__dict__, "id": None}))

        metrics = StatisticsEngine(pooled).overall(1)
        avg_pnl = (sum(pnls, Decimal("0")) / runs).quantize(Decimal("0.01")) if runs else Decimal("0")
        scores.append(StrategyScore(
            key=key, runs=runs, combine_pass_rate=round(passes / runs, 3) if runs else 0.0,
            avg_pnl=avg_pnl, metrics=metrics,
        ))

    # Rank: prefer positive expectancy, then profit factor, then pass rate.
    def rank_key(s: StrategyScore):
        exp = float(s.metrics.expectancy or Decimal("0"))
        pf = s.metrics.profit_factor or 0.0
        return (exp, pf, s.combine_pass_rate)

    scores.sort(key=rank_key, reverse=True)
    return scores
