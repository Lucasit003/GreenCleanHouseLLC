"""Search across strategy configurations to see which lifts the Combine pass-rate.

    python scripts/strategy_search.py [runs_per_config]

⚠️  SYNTHETIC data. Maximizing pass-rate on synthetic markets is OVERFITTING —
the point here is to see which setups are robust across varied conditions, not
to pick a 'winner' to trade. Real data over time is the only honest judge.
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
from tradingsys.engines.strategy.strategies.ema_cross import EmaCrossStrategy  # noqa: E402
from tradingsys.engines.strategy.strategies.range_fade import RangeFadeStrategy  # noqa: E402
from tradingsys.engines.strategy.strategies.trend_pullback import TrendPullbackStrategy  # noqa: E402

# Each config is a factory returning a FRESH list of strategy instances.
CONFIGS: dict[str, callable] = {
    "breakout rr2":        lambda: [BreakoutStrategy(rr=2.0)],
    "breakout rr3":        lambda: [BreakoutStrategy(rr=3.0)],
    "breakout rr1.5":      lambda: [BreakoutStrategy(rr=1.5)],
    "trend+breakout":      lambda: [TrendPullbackStrategy(rr=2.0), BreakoutStrategy(rr=2.0)],
    "trend+brk+fade":      lambda: [TrendPullbackStrategy(rr=2.0), BreakoutStrategy(rr=2.0),
                                    RangeFadeStrategy(rr=1.5)],
    "all four":            lambda: [TrendPullbackStrategy(), BreakoutStrategy(),
                                    EmaCrossStrategy(), RangeFadeStrategy()],
}


def run_config(make_strats, runs: int, risk_pct: Decimal) -> dict:
    pnls, states = [], []
    for i in range(runs):
        rng = random.Random(2000 + i)
        drift = rng.uniform(-0.35, 0.40)
        vol = rng.uniform(1.0, 2.6)
        system = build_system(seed=2000 + i, drift=drift, volatility=vol, days=6,
                              risk_per_trade_pct=risk_pct, strategy_list=make_strats())
        st = run_auto(system)
        pnls.append(float(st["realized_pnl"])); states.append(st["state"])
    return {
        "avg": statistics.mean(pnls), "median": statistics.median(pnls),
        "green": 100 * sum(1 for p in pnls if p > 0) / runs,
        "pass": 100 * states.count("passed") / runs,
        "fail": 100 * states.count("failed") / runs,
    }


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    risk_pct = Decimal("0.01")
    print(f"Strategy search: {runs} runs/config, 1% risk, ${'50000'} Topstep 50K rules "
          f"(SYNTHETIC)\n")
    header = f"{'config':<18}{'avg P&L':>10}{'median':>10}{'% green':>9}{'pass%':>8}{'fail%':>8}"
    print(header); print("-" * len(header))
    rows = []
    for name, make in CONFIGS.items():
        r = run_config(make, runs, risk_pct)
        rows.append((name, r))
        print(f"{name:<18}{r['avg']:>10.0f}{r['median']:>10.0f}{r['green']:>8.0f}%"
              f"{r['pass']:>7.0f}%{r['fail']:>7.0f}%")
    best = max(rows, key=lambda x: x[1]["pass"])
    print(f"\nHighest pass-rate: {best[0]} ({best[1]['pass']:.0f}%)")
    print("⚠ synthetic + no fees/slippage. This is overfitting-prone — validate on real "
          "data over time before trusting any config.")


if __name__ == "__main__":
    main()
