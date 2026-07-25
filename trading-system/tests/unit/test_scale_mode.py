"""scale_size_near_limit resolves 'stuck' accounts instead of leaving them pinned."""
from __future__ import annotations

import random
from decimal import Decimal

from tradingsys.app.runner import build_system, run_auto
from tradingsys.engines.strategy.strategies.breakout import BreakoutStrategy
from tradingsys.engines.strategy.strategies.trend_pullback import TrendPullbackStrategy


def _strats():
    return [TrendPullbackStrategy(rr=2.0), BreakoutStrategy(rr=2.0)]


def _resolve_rate(scale: bool, n: int = 25) -> float:
    resolved = 0
    for i in range(n):
        rng = random.Random(6000 + i)
        s = build_system(seed=6000 + i, drift=rng.uniform(-0.3, 0.4),
                         volatility=rng.uniform(1.0, 2.5), days=20,
                         risk_per_trade_pct=Decimal("0.01"), strategy_list=_strats())
        st = run_auto(s, commission_per_contract=Decimal("4.00"), slippage_ticks=1,
                      scale_size_near_limit=scale)
        if st["state"] in ("passed", "failed"):
            resolved += 1
    return resolved / n


def test_scale_mode_resolves_more_accounts():
    # scaling size near the limit should leave far fewer accounts 'stuck'
    assert _resolve_rate(scale=True) > _resolve_rate(scale=False)
