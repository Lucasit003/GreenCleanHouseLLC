#!/usr/bin/env python3
"""Local runner for the trading system. Run this on YOUR computer.

    python run.py advise      # tell me the trade right now (places nothing)
    python run.py auto        # make the trades autonomously (PAPER) + report
    python run.py report      # run a paper session and show the practice report
    python run.py backtest --csv data/ES.csv   # backtest on REAL historical bars

Options:  --profile topstep_50k   --seed 7   --csv <file>   --tf 5m

Everything is PAPER/simulated until you connect a real data feed and broker
adapter locally (see docs/09_RUN_LOCALLY.md). Nothing here places a real order.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from tradingsys.app.runner import advise, build_system, run_auto  # noqa: E402
from tradingsys.dashboard.report import render_report  # noqa: E402
from tradingsys.domain.types import RecommendationAction  # noqa: E402


def _opt(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def cmd_advise(profile: str, seed: int) -> None:
    system = build_system(profile_key=profile, seed=seed)
    context, recs = advise(system)
    print(f"Market read ({context.instrument} {context.timeframe}): "
          f"trend={context.trend.value}, structure={context.structure.value}, "
          f"volatility={context.volatility_regime.value}, session={context.session.value}\n")
    if not recs:
        print("→ No setup right now. Recommendation: WAIT (patience — no edge present).")
        return
    for r in recs:
        print(f"→ {r.action.value.upper()}  {r.setup.strategy_key} "
              f"{(r.direction.value if r.direction else '')}")
        if r.action is RecommendationAction.ENTER:
            print(f"   entry {r.entry}  stop {r.stop}  target {r.target}  "
                  f"size {r.suggested_size}  score {r.score}")
        else:
            reason = r.explanation.get("wait_reason") or r.explanation.get("avoid_reason") or ""
            print(f"   reason: {reason}  (score {r.score})")
    print("\n(advisory only — no order placed)")


def cmd_auto(profile: str, seed: int, show_report: bool,
             csv_path: str | None = None, tf: str = "5m") -> None:
    system = build_system(profile_key=profile, seed=seed, csv_path=csv_path, timeframe=tf)
    if csv_path:
        print(f"(real historical data: {csv_path} — {len(system.bars)} bars)\n")
    status = run_auto(system)
    verdict = {"passed": "✅ PASSED", "failed": "❌ FAILED", "active": "… still ACTIVE"}
    print(f"=== {status['profile']} — autonomous PAPER session (seed={seed}) ===\n")
    print(f"Result: {verdict.get(status['state'], status['state'])}"
          + (f"  ({status['fail_reason']})" if status['fail_reason'] else ""))
    print(f"Realized P&L: ${status['realized_pnl']}  (target ${status['profit_target']}, "
          f"{status['profit_progress_pct']}%)")
    print(f"Trailing max-loss @ ${status['trailing_threshold']}  (room ${status['max_loss_room']})")
    print(f"Trades — opened {status['opened']}, closed {status['closed']}, "
          f"blocked by rules {status['blocked_by_rules']}\n")
    if show_report:
        confidences = [system.learning.update_confidence(s.key)
                       for s in system.strategies.enabled_strategies()]
        print(render_report(
            overall=system.stats.overall(1),
            by_strategy=system.stats.by_scope(1, "by_strategy"),
            confidences=confidences,
            flags=system.perf.review(1),
            recent_trades=list(system.trades.query(1)),
        ))
    print("\n(PAPER — no real orders. Connect a broker locally to trade live; see docs/09)")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "advise"
    profile = _opt("--profile", "topstep_50k")
    seed = int(_opt("--seed", "7"))
    csv_path = _opt("--csv", "") or None
    tf = _opt("--tf", "5m")
    if cmd == "advise":
        cmd_advise(profile, seed)
    elif cmd == "auto":
        cmd_auto(profile, seed, show_report=False, csv_path=csv_path, tf=tf)
    elif cmd == "report":
        cmd_auto(profile, seed, show_report=True, csv_path=csv_path, tf=tf)
    elif cmd == "backtest":
        cmd_auto(profile, seed, show_report=True, csv_path=csv_path, tf=tf)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
