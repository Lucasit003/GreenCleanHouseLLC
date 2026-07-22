# Deliverable 6 — Implementation Order

> **Build status (paper):** Steps 1–3 and 5–13 are implemented and covered by a
> passing test suite (`python -m pytest`, 30 tests, no external infra). Step 4
> ships as a text/markdown dashboard (`dashboard/report.py`); Step 14's
> execution half (paper) is done, its web-API half is deferred. **Step 15 (live
> Topstep) is intentionally NOT built** — the system is complete for paper
> practice. Run the whole pipeline with `python scripts/paper_demo.py`.

Build **one tested module at a time**. Each step lists its dependency, exit
criteria (definition of done), and the tests that must pass before advancing.
Nothing here is built ahead of its turn — the interfaces already exist, so each
step fills in a concrete implementation behind a contract that won't move.

## Ordering principle

We sequence by **dependency + risk-first + earliest usefulness**:

1. Storage and the journal come first because the journal is valuable on day one
   and every later module reads/writes through it.
2. The Risk Engine is built *before* anything can act on a recommendation, and it
   holds veto power the moment it exists.
3. Execution comes last and starts in paper mode — it's the only module that can
   move real money, so it's built when everything gating it is already proven.

## Step-by-step

### Step 1 — Database & repositories  *(depends on: schema)*
Implement `db/migrations/`, a connection layer, and concrete
`persistence/*Repository` classes satisfying `interfaces/repository.py`.
Seed `instruments` and one `risk_rule_versions` row from config.
**Done when:** migrations apply cleanly; repositories pass CRUD unit tests and a
round-trip integration test against a real Postgres.

### Step 2 — Journal Engine  *(depends on: 1)*
Implement `JournalEngine`: open/close/annotate; compute net P&L, R-multiple,
result at close. **Done when:** a trade can be opened, closed, and reviewed;
P&L/R-multiple math is unit-tested against known fixtures.

### Step 3 — Statistics Engine v1  *(depends on: 2)*
Win rate, avg winner/loser, expectancy, profit factor, max drawdown, plus
`by_strategy`/`by_session`/`by_time_of_day`. All from own journal data.
**Done when:** metrics match hand-computed fixtures; `has_sufficient_sample`
guards small samples.

### Step 4 — Dashboard v1  *(depends on: 2, 3)*
Read-only view of journal + core stats. **Done when:** the trader can log trades
(via API/CLI) and see honest own-data analytics. *This is the Phase 1 MVP — it
earns its keep before any automation exists.*

### Step 5 — Market Data ingestion  *(depends on: 1)*
First adapter behind `MarketDataProvider` (start with a historical/CSV or single
vendor adapter). Normalize to `Bar`, persist to `market_bars`.
**Done when:** history loads reproducibly; a streaming stub yields closed bars.

### Step 6 — Indicators + Market Analysis Engine  *(depends on: 5)*
Pure indicator functions (EMA, VWAP, ATR, volume) each unit-tested in isolation,
then `MarketAnalysisEngine.analyze` producing a labeled `MarketContext`.
**Done when:** indicators match reference values; analysis labels a known
fixture window correctly and marks genuine ambiguity as `UNKNOWN`.

### Step 7 — Strategy Engine + first strategies  *(depends on: 6)*
`StrategyEngine` registry plus 2–3 strategies (e.g. trend pullback, ORB) as
`Strategy` implementations that declare ideal/poor conditions and emit `Setup`s.
**Done when:** each strategy emits expected setups on fixture data and correctly
emits none when its conditions are absent.

### Step 8 — Backtesting harness  *(depends on: 7, 2)*
Replay historical bars through strategies; write hypothetical trades through the
**same** Journal schema. **Done when:** a backtest is reproducible (same inputs →
same results) and its output feeds the Statistics Engine unchanged.

### Step 9 — Risk Management Engine  *(depends on: 1)*  **← highest priority**
Position sizing, max daily loss/drawdown, trade-count & exposure caps, Topstep
rules from config; `evaluate` returns authoritative approve/veto; rule changes
require a human approver. **Done when:** every limit has a passing veto test, and
a property test proves no code path applies a rule change without `approved_by`.

### Step 10 — Decision Framework  *(depends on: 6, 7, 9, +news later)*
Compose MarketContext + setups + own-data stats + confidence + **risk veto** into
a scored, explainable `Recommendation`, including `WAIT`. **Done when:** a vetoed
setup always yields `AVOID`; weak evidence always yields `WAIT`; every
recommendation carries a complete factor breakdown.

### Step 11 — News Engine  *(depends on: 1)*
Calendar adapter → `news_events`; `news_risk` blackout windows. Wire into the
Decision Framework. **Done when:** setups inside a high-impact window are
suppressed/down-weighted with an explainable reason.

### Step 12 — Statistics v2 + Learning Engine  *(depends on: 3, 8)*
Sharpe, avg hold, slices by volatility/news/weekday; confidence scoring with
overfitting guards; `LearningEngine` emits proposals only. **Done when:**
confidence updates require a minimum sample; a test proves the engine cannot
apply a `risk_change` (only propose it).

### Step 13 — Performance Review Engine  *(depends on: 2, 3)*
Detect overtrading/revenge/FOMO/plan-deviation; emit `BehaviorFlag`s with
corrective advice. **Done when:** each pattern is detected on a crafted fixture
and not on clean data.

### Step 14 — Execution Engine (paper) + API/Dashboard v2  *(depends on: 9, 10)*
`PaperExecutionEngine` (simulated fills) behind `ExecutionEngine`; API approve/
reject flow; live recommendation feed + risk status. **Done when:** `submit`
refuses without an approved risk decision AND `human_confirmed=True`; the full
loop runs end-to-end in paper mode.

### Step 15 — Topstep live adapter + Hardening  *(depends on: 14)*
`TopstepExecutionEngine` behind the same interface; observability, audit trails,
backups, kill-switch (`flatten`), secrets management, incident runbook.
**Done when:** live is reachable but remains off by default; promotion to live is
a deliberate, audited, human action; a dry-run shadow matches expectations.

## Sequence at a glance

```
1 DB → 2 Journal → 3 Stats v1 → 4 Dashboard v1   ── Phase 1 MVP (usable!)
                                   │
5 Market Data → 6 Analysis ────────┤              ── Phase 2
                                   │
7 Strategy → 8 Backtest            │
9 Risk (veto) → 10 Decision ───────┤              ── Phase 3 (core)
                                   │
11 News ───────────────────────────┤              ── Phase 4
12 Learning → 13 Perf Review ──────┤              ── Phase 5
                                   │
14 Execution(paper)+API/Dash v2 ───┤              ── Phase 6
15 Topstep live + Hardening ───────┘              ── Phase 7
```

Each number is a merge-ready unit: implement, test, document, then move on.
