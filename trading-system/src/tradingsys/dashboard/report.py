"""Dashboard v1 (Step 4) — a plain-text/markdown read-only view.

Renders the journal + own-data analytics + behavior flags + strategy confidence
into a report you can read in a terminal. A web UI (Dashboard v2, Step 14) will
consume the same engine outputs later; this keeps the practice loop dependency-free.
"""
from __future__ import annotations

from typing import Sequence

from ..domain.types import BehaviorFlag, Confidence, PerformanceMetrics, Trade


def _fmt(v: object) -> str:
    return "-" if v is None else str(v)


def render_report(
    *,
    overall: PerformanceMetrics,
    by_strategy: Sequence[PerformanceMetrics],
    confidences: Sequence[Confidence],
    flags: Sequence[BehaviorFlag],
    recent_trades: Sequence[Trade],
) -> str:
    lines: list[str] = []
    lines.append("# Trading Practice Report (paper)\n")

    lines.append("## Overall performance (own data)")
    lines.append(f"- Trades: {overall.sample_size}")
    lines.append(f"- Win rate: {_fmt(overall.win_rate)}")
    lines.append(f"- Expectancy / trade: {_fmt(overall.expectancy)}")
    lines.append(f"- Profit factor: {_fmt(overall.profit_factor)}")
    lines.append(f"- Max drawdown: {_fmt(overall.max_drawdown)}")
    lines.append(f"- Sharpe (per-trade): {_fmt(overall.sharpe)}")
    lines.append(f"- Avg hold (min): {_fmt(overall.avg_hold_min)}\n")

    lines.append("## By strategy")
    if by_strategy:
        lines.append("| strategy | n | win% | expectancy | profit factor |")
        lines.append("|---|---|---|---|---|")
        for m in by_strategy:
            lines.append(f"| {m.scope_key} | {m.sample_size} | {_fmt(m.win_rate)} "
                         f"| {_fmt(m.expectancy)} | {_fmt(m.profit_factor)} |")
    else:
        lines.append("_no closed trades yet_")
    lines.append("")

    lines.append("## Strategy confidence (evidence-based, overfitting-guarded)")
    for c in confidences:
        lines.append(f"- {c.strategy_key}: {c.value} (n={c.sample_size}, {c.method})")
    lines.append("")

    lines.append("## Behavior flags (psychology coach)")
    if flags:
        for f in flags:
            lines.append(f"- [{f.severity}] {f.pattern}: {f.recommendation}")
    else:
        lines.append("_none detected_")
    lines.append("")

    lines.append("## Recent trades")
    lines.append("| id | strat | dir | qty | entry | exit | net | R | result |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for t in recent_trades[-15:]:
        lines.append(
            f"| {t.id} | {_fmt(t.strategy_key)} | {t.direction.value} | {t.quantity} "
            f"| {t.entry_price} | {_fmt(t.exit_price)} | {_fmt(t.net_pnl)} "
            f"| {_fmt(round(t.r_multiple, 2) if t.r_multiple is not None else None)} "
            f"| {t.result.value} |"
        )
    return "\n".join(lines)
