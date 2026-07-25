"""Monte-Carlo backtest: run the system N times across varied market conditions
and report the distribution of results at different risk-per-trade levels.

    python scripts/monte_carlo.py [N] [runs_per_risk]

⚠️  Runs on SYNTHETIC data (the proxy here blocks real market data). Each run
uses a different randomized market (drift + volatility) so the sample spans
uptrends, downtrends, and chop — but it is NOT real past prices. Treat the
numbers as a study of the machinery + risk sizing, not a forecast.
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

START = Decimal("50000")


def one_run(seed: int, risk_pct: Decimal) -> dict:
    rng = random.Random(seed)
    drift = rng.uniform(-0.35, 0.40)          # varied market direction
    vol = rng.uniform(1.0, 2.6)               # varied volatility
    system = build_system(seed=seed, drift=drift, volatility=vol, days=6,
                          risk_per_trade_pct=risk_pct)
    return run_auto(system)


def summarize(pnls: list[float], states: list[str]) -> dict:
    n = len(pnls)
    passed = states.count("passed")
    failed = states.count("failed")
    profitable = sum(1 for p in pnls if p > 0)
    return {
        "runs": n,
        "avg_pnl": statistics.mean(pnls),
        "median_pnl": statistics.median(pnls),
        "best": max(pnls),
        "worst": min(pnls),
        "pct_profitable": 100 * profitable / n,
        "pass_rate": 100 * passed / n,
        "fail_rate": 100 * failed / n,
    }


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print(f"Monte-Carlo: {runs} runs per risk level on a ${START} account "
          f"(Topstep 50K rules; SYNTHETIC varied markets)\n")
    header = (f"{'risk/trade':>11}{'avg P&L':>11}{'median':>10}{'best':>9}"
              f"{'worst':>9}{'% green':>9}{'pass%':>8}{'fail%':>8}")
    print(header); print("-" * len(header))
    for risk_pct in (Decimal("0.01"), Decimal("0.02"), Decimal("0.03")):
        pnls, states = [], []
        for i in range(runs):
            st = one_run(seed=1000 + i, risk_pct=risk_pct)
            pnls.append(float(st["realized_pnl"])); states.append(st["state"])
        s = summarize(pnls, states)
        print(f"{str(risk_pct.quantize(Decimal('0.00'))):>11}"
              f"{s['avg_pnl']:>11.0f}{s['median_pnl']:>10.0f}{s['best']:>9.0f}"
              f"{s['worst']:>9.0f}{s['pct_profitable']:>8.0f}%"
              f"{s['pass_rate']:>7.0f}%{s['fail_rate']:>7.0f}%")
    print("\nPass = hit +$3,000 target under the rules. Fail = breached the $2,000 "
          "trailing max loss.\n⚠ synthetic data, idealized fills (no slippage/fees) — "
          "real results would be worse.")


if __name__ == "__main__":
    main()
