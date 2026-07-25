"""Realistic Combine test WITH transaction costs (commission + slippage).

    python scripts/realistic_test.py [runs_per_config]

Costs applied (ES, per contract): $4.00 round-turn commission + 1 tick ($12.50)
slippage on entry AND exit. This is the single biggest realism upgrade over the
free-fill runs.

⚠️  Data is still SYNTHETIC (real prices are blocked in this environment). So
this shows how costs erode the edge and how the bots behave — it is not a
forecast of real results.
"""
from __future__ import annotations

import random
import statistics
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tradingsys.app.runner import build_system, run_auto  # noqa: E402
from tradingsys.engines.strategy.strategies.breakout import BreakoutStrategy  # noqa: E402
from tradingsys.engines.strategy.strategies.range_fade import RangeFadeStrategy  # noqa: E402
from tradingsys.engines.strategy.strategies.trend_pullback import TrendPullbackStrategy  # noqa: E402

COMMISSION = Decimal("4.00")   # round-turn $ per contract
SLIPPAGE_TICKS = 1             # each side

CONFIGS = {
    "breakout only":   lambda: [BreakoutStrategy(rr=2.0)],
    "trend+breakout":  lambda: [TrendPullbackStrategy(rr=2.0), BreakoutStrategy(rr=2.0)],
    "trend+brk+fade":  lambda: [TrendPullbackStrategy(rr=2.0), BreakoutStrategy(rr=2.0),
                                RangeFadeStrategy(rr=1.5)],
}


def run_config(make, runs, costs: bool):
    pnls, states = [], []
    for i in range(runs):
        rng = random.Random(3000 + i)
        system = build_system(seed=3000 + i, drift=rng.uniform(-0.35, 0.40),
                              volatility=rng.uniform(1.0, 2.6), days=6,
                              risk_per_trade_pct=Decimal("0.01"), strategy_list=make())
        st = run_auto(system,
                      commission_per_contract=COMMISSION if costs else Decimal("0"),
                      slippage_ticks=SLIPPAGE_TICKS if costs else 0)
        pnls.append(float(st["realized_pnl"])); states.append(st["state"])
    return {
        "avg": statistics.mean(pnls), "median": statistics.median(pnls),
        "green": 100 * sum(1 for p in pnls if p > 0) / runs,
        "pass": 100 * states.count("passed") / runs,
        "fail": 100 * states.count("failed") / runs,
    }


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    print(f"Realistic test: {runs} runs/config, 1% risk, ${'50000'} Topstep 50K rules")
    print(f"Costs: ${COMMISSION} round-turn + {SLIPPAGE_TICKS} tick slippage/side  (SYNTHETIC data)\n")
    hdr = f"{'config':<17}{'':<8}{'avg P&L':>10}{'median':>10}{'% green':>9}{'pass%':>8}{'fail%':>8}"
    print(hdr); print("-" * len(hdr))
    for name, make in CONFIGS.items():
        free = run_config(make, runs, costs=False)
        real = run_config(make, runs, costs=True)
        print(f"{name:<17}{'no-cost':<8}{free['avg']:>10.0f}{free['median']:>10.0f}"
              f"{free['green']:>8.0f}%{free['pass']:>7.0f}%{free['fail']:>7.0f}%")
        print(f"{'':<17}{'REAL':<8}{real['avg']:>10.0f}{real['median']:>10.0f}"
              f"{real['green']:>8.0f}%{real['pass']:>7.0f}%{real['fail']:>7.0f}%")
    print("\nREAL = with commission + slippage. Pass = hit +$3,000; Fail = breached -$2,000.")


if __name__ == "__main__":
    main()
