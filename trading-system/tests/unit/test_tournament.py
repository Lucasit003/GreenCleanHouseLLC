"""Strategy bake-off harness — isolates strategies and ranks by evidence."""
from __future__ import annotations

from tradingsys.backtest.tournament import run_tournament
from tradingsys.engines.strategy.strategies.breakout import BreakoutStrategy
from tradingsys.engines.strategy.strategies.ema_cross import EmaCrossStrategy


def test_tournament_ranks_strategies():
    facs = {"breakout": BreakoutStrategy, "ema_cross": EmaCrossStrategy}
    scores = run_tournament(
        facs, seeds=(7,), scenarios=[("uptrend", dict(drift=0.4, volatility=1.5))]
    )
    assert len(scores) == 2
    keys = {s.key for s in scores}
    assert keys == {"breakout", "ema_cross"}
    # sorted by expectancy descending
    exps = [float(s.metrics.expectancy or 0) for s in scores]
    assert exps == sorted(exps, reverse=True)
    # each strategy was run in isolation the expected number of times
    assert all(s.runs == 1 for s in scores)


def test_pass_rate_is_a_fraction():
    facs = {"breakout": BreakoutStrategy}
    scores = run_tournament(facs, seeds=(7, 21),
                            scenarios=[("uptrend", dict(drift=0.4, volatility=1.5))])
    assert 0.0 <= scores[0].combine_pass_rate <= 1.0
    assert scores[0].runs == 2
