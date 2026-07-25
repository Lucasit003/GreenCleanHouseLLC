"""Does more time help? Sweep the evaluation window (1 week -> ~1 month) with
realistic costs and see how pass/fail/unresolved rates change.

    python scripts/window_sweep.py [runs_per_window]

The Combine has no tight time limit, so a trader gets weeks. This shows whether
that extra time resolves runs toward PASS or toward FAIL — which depends
entirely on whether there's an edge after costs.

⚠️  SYNTHETIC data; $4 round-turn + 1 tick/side slippage. Not a forecast.
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

COMMISSION = Decimal("4.00")
SLIP = 1
WINDOWS = [("~1 week", 6), ("~2 weeks", 12), ("~3 weeks", 18), ("~1 month", 26)]


def strat():
    return [TrendPullbackStrategy(rr=2.0), BreakoutStrategy(rr=2.0), RangeFadeStrategy(rr=1.5)]


def run_window(days: int, runs: int):
    pnls, states = [], []
    for i in range(runs):
        rng = random.Random(4000 + i)
        system = build_system(seed=4000 + i, drift=rng.uniform(-0.35, 0.40),
                              volatility=rng.uniform(1.0, 2.6), days=days,
                              risk_per_trade_pct=Decimal("0.01"), strategy_list=strat())
        st = run_auto(system, commission_per_contract=COMMISSION, slippage_ticks=SLIP)
        pnls.append(float(st["realized_pnl"])); states.append(st["state"])
    n = len(states)
    return {
        "avg": statistics.mean(pnls),
        "pass": 100 * states.count("passed") / n,
        "fail": 100 * states.count("failed") / n,
        "neither": 100 * states.count("active") / n,
    }


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    print(f"Window sweep: {runs} runs each, trend+brk+fade, 1% risk, realistic costs "
          f"(SYNTHETIC)\n")
    hdr = f"{'window':<12}{'avg P&L':>10}{'pass%':>8}{'fail%':>8}{'unresolved%':>13}"
    print(hdr); print("-" * len(hdr))
    for label, days in WINDOWS:
        r = run_window(days, runs)
        print(f"{label:<12}{r['avg']:>10.0f}{r['pass']:>7.0f}%{r['fail']:>7.0f}%{r['neither']:>12.0f}%")
    print("\nunresolved = ran out of data without hitting +$3,000 or -$2,000.")
    print("If more time shifts runs into PASS, there's an edge; if into FAIL, there isn't.")


if __name__ == "__main__":
    main()
