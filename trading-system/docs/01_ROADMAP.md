# Deliverable 1 — Project Roadmap

The build is milestone-driven. We do **not** attempt the whole platform at once.
Each milestone delivers one working, tested, documented capability that stands
on its own before the next begins.

## Guiding constraints

- **Vertical slices over horizontal layers.** Each milestone should let the
  trader *do something real*, even if narrow.
- **Test before advance.** A module is "done" only when it has unit tests, an
  integration test against its neighbors, and a short usage doc.
- **Risk first, always.** The Risk Engine gates every recommendation from the
  moment it exists. Nothing bypasses it later.
- **Backtest ≠ live.** Anything that touches a broker starts in dry-run /
  paper mode and stays there until explicitly promoted by a human.

---

## Phase 0 — Architecture (this deliverable set) ✅

Roadmap, folder structure, DB schema, data sources, module interfaces,
implementation order, and ADRs. No engine code. **Done.**

## Phase 1 — Foundation & Journal (MVP that earns its keep on day one)

**Goal:** a trustworthy trade journal + analytics, usable immediately even with
zero automation.

- M1.1 **Database** — schema migrations, connection layer, repository
  implementations for core tables.
- M1.2 **Journal Engine** — record/read/update trades and setups; screenshot
  attachment; mistakes & lessons capture.
- M1.3 **Statistics Engine (v1)** — win rate, avg winner/loser, expectancy,
  profit factor, max drawdown, per-strategy / per-session / per-time-of-day
  breakdowns computed from the trader's own journal.
- M1.4 **Dashboard (v1)** — read-only view of journal + core stats.

**Definition of done:** the trader can log trades and see honest, own-data
analytics. This alone is valuable and validates the schema.

## Phase 2 — Market Data & Analysis

**Goal:** turn raw market data into structured, explainable observations.

- M2.1 **Market Data ingestion** — historical + streaming bars for target
  contracts (ES, NQ, etc.); normalization; storage.
- M2.2 **Market Analysis Engine** — trend (HH/HL/LH/LL), structure
  (range/accumulation/distribution/breakout/failed breakout/liquidity sweep),
  volatility regime (via ATR), key S/R levels, session context.
- M2.3 Indicator library — EMA, VWAP, ATR, volume/volume-profile primitives,
  RSI/MACD/Bollinger — each as an independent, testable function.

**Definition of done:** given a contract + timeframe, the engine emits a
structured `MarketContext` with every factor labeled and sourced.

## Phase 3 — Strategy & Risk (the core of decision support)

**Goal:** produce **explainable, risk-gated** trade recommendations.

- M3.1 **Strategy Engine** — pluggable strategy modules (trend pullback, ORB,
  VWAP, EMA pullback, breakout retest, double top/bottom, flags/triangles,
  etc.). Each strategy declares its ideal/poor conditions and emits candidate
  setups — never a naked "buy".
- M3.2 **Backtesting harness** — replay historical bars through strategies;
  record hypothetical outcomes into the same schema the Journal uses.
- M3.3 **Risk Management Engine** — position sizing, risk-per-trade, max daily
  loss, max drawdown, exposure caps, daily/weekly trade limits. **Hard veto
  power** over every recommendation. Encodes Topstep account rules.
- M3.4 **Decision Framework** — combine MarketContext + strategy signal + risk
  check + historical performance of similar setups + current confidence into a
  single scored, explainable recommendation (including "wait").

**Definition of done:** the system produces a recommendation with a full factor
breakdown, and the Risk Engine can and does veto.

## Phase 4 — News & Context

- M4.1 **News Engine** — economic calendar (FOMC, CPI, PPI, GDP, employment,
  Fed speakers), event severity, blackout windows.
- M4.2 Integrate news risk into the Decision Framework (e.g. suppress or
  down-weight setups inside high-impact event windows).

## Phase 5 — Learning & Performance Review

- M5.1 **Statistics Engine (v2)** — Sharpe, avg hold time, performance sliced by
  market/time/volatility/news/day-of-week/session; strategy confidence scoring.
- M5.2 **Learning Engine** — update per-strategy confidence from long-term
  evidence with overfitting guards (minimum sample size, walk-forward, decay).
  **Never** touches risk rules; proposes changes for human approval only.
- M5.3 **Performance Review Engine** — periodic reviews; detect behavioral
  patterns (overtrading, revenge trading, FOMO, deviation from plan) and
  recommend corrective actions.

## Phase 6 — Execution (paper first, always human-confirmed)

- M6.1 **Execution Engine** — Topstep connectivity behind the same interface;
  **paper/dry-run by default**; every live order requires explicit human
  confirmation; enforces Risk Engine veto at the boundary.
- M6.2 **API Layer + Dashboard (v2)** — full read/write API; live recommendation
  feed; risk status; approve/reject workflow.

## Phase 7 — Hardening

- Observability, audit trails, backups, reconciliation, alerting, and a
  documented incident runbook. Broker credentials in a secrets manager, never
  in the repo.

---

## Cross-cutting, from day one

- **Testing** — unit + integration per module; backtests are reproducible.
- **Auditability** — every recommendation, risk decision, and rule change is
  persisted with its inputs.
- **Config over code** — contract specs, risk limits, and account rules live in
  config/DB, not hard-coded.
- **Modularity** — every module hides behind the interfaces in doc 5 so it can
  be replaced without touching its neighbors.

## Milestone dependency graph

```
Phase 0 ─▶ Phase 1 (DB, Journal, Stats v1, Dashboard v1)
                │
                ▼
           Phase 2 (Market Data, Analysis)
                │
                ▼
           Phase 3 (Strategy, Backtest, Risk, Decision)
                │
        ┌───────┴────────┐
        ▼                ▼
   Phase 4 (News)   Phase 5 (Learning, Perf Review)
        └───────┬────────┘
                ▼
           Phase 6 (Execution — paper, human-confirmed)
                │
                ▼
           Phase 7 (Hardening)
```
