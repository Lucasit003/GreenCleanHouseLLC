# Deliverable 3 — Database Schema

The canonical, runnable schema is [`db/schema.sql`](../db/schema.sql) — that file
is the source of truth; this document explains it.

**Engine:** PostgreSQL 15+. Market bars are a natural fit for a TimescaleDB
hypertable, but that's an optional optimization, not a requirement.

## Design rules

- **Money is `NUMERIC`, never float.** Floating-point rounding is unacceptable in
  P&L. Prices use `NUMERIC(18,8)`; cash amounts use `NUMERIC(18,2)`.
- **Time is `TIMESTAMPTZ` in UTC.** Sessions are derived at read time using the
  instrument's `session_tz`.
- **Append-only where it matters.** Confidence scores and risk-rule versions are
  never mutated in place — we keep the history to audit trajectories and to
  detect overfitting.
- **The decision chain is fully persisted.** `setups → recommendations →
  risk_decisions → trades` records not just *what* was decided but *why*,
  satisfying the explainability and auditability principles.

## Table map

| Table | Role | Written by |
|-------|------|------------|
| `instruments` | Contract specs (tick size/value, sessions, margin) | Config/seed |
| `market_bars` | OHLCV history & stream | Market Data Engine |
| `strategies` | Registry of pluggable strategies + documented conditions | Strategy Engine |
| `strategy_confidence` | **Time series** of evidence-based confidence | Learning Engine |
| `risk_rule_versions` | **Versioned, human-approved** risk rules | Risk Engine / human |
| `accounts` | Topstep (and future) accounts; paper by default | Config |
| `market_contexts` | Labeled market state snapshots (explainability) | Market Analysis Engine |
| `setups` | Candidate opportunities from strategies | Strategy Engine |
| `recommendations` | Scored, explainable output (incl. `wait`/`avoid`) | Decision Framework |
| `risk_decisions` | Every risk check, pass **or** veto | Risk Engine |
| `trades` | The journal — one row per executed trade | Journal Engine |
| `trade_fills` | Scale-in/out fills | Journal / Execution |
| `news_events` | Economic calendar | News Engine |
| `analytics_snapshots` | Materialized metrics by scope | Statistics Engine |
| `behavior_flags` | Psychology/behavior detections | Performance Review Engine |
| `learning_proposals` | Change proposals awaiting **human approval** | Learning Engine |

## The core decision & audit chain

```
market_contexts ──┐
                  ▼
strategies ──▶ setups ──▶ recommendations ──▶ risk_decisions ──▶ trades ──▶ trade_fills
                                                     │                          │
                              (veto or approve, full check log)      (realized P&L, R-multiple,
                                                                      mistakes, lessons, screenshot)
```

Every `trade` links back to the `recommendation`, `setup`, `strategy`, and
`risk_decision` that produced it. This is what lets analytics answer "how does
*this strategy* perform *in this session* under *high volatility*" from the
trader's **own** data.

## How the sacred rules are enforced at the data layer

- `risk_rule_versions` is **insert-only**. Changing a limit means inserting a new
  version with `approved_by` / `approved_at` populated by a human. The Learning
  Engine may only write to `learning_proposals` with `kind='risk_change'` and
  `status='pending'`; it can never insert an approved risk version.
- `accounts.is_paper` defaults to `TRUE`. Promotion to live is a deliberate,
  audited change.
- `strategy_confidence` requires a `sample_size` and `method` on every row, so a
  confidence score can never exist without stating the evidence behind it.

## Key metrics and where they live

Realized per-trade numbers (`gross_pnl`, `net_pnl`, `r_multiple`, `result`) are
computed at trade close and **stored on the `trades` row** for fast analytics.
Aggregate metrics (win rate, expectancy, profit factor, drawdown, Sharpe, avg
hold time) are computed by the Statistics Engine and materialized into
`analytics_snapshots`, sliced by `scope`/`scope_key` (overall, by strategy, by
session, by time-of-day, by volatility regime, by news condition, by weekday).

## Migrations

Phase 1 introduces `db/migrations/` with versioned, forward-only migrations. The
`schema.sql` file remains the readable canonical reference; migrations are the
mechanism to reach it and evolve it.
