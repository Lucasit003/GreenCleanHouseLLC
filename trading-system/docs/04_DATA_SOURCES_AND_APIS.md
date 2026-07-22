# Deliverable 4 — Data Sources & APIs

This document lists the external data the system needs, the integration points,
and — importantly — the **abstraction boundaries** that keep any single vendor
replaceable. We commit to *interfaces*, not vendors.

## Principle: vendors sit behind adapters

Every external dependency is reached through one of our interfaces
(`interfaces/market_data.py`, `interfaces/execution.py`, `interfaces/news.py`).
A vendor is an *adapter* implementing that interface. Swapping Databento for
Polygon, or Topstep for another prop firm, is a new adapter — never a change to
engine logic. This directly serves the brief's "keep additional brokers and prop
firms modular" requirement.

---

## 1. Market data (bars, and later order flow)

**What we need**
- Historical OHLCV for target CME futures (ES, NQ, and others) at 1m/5m/15m/1h/1d
  for backtesting and analysis.
- Real-time / near-real-time bars for live decision support.
- Contract specifications (tick size, tick value, sessions, margin, rollover
  calendar).
- Later phases: level-2 / order flow, volume profile, delta/footprint inputs.

**Candidate providers** (evaluate on cost, latency, history depth, futures
coverage — decide with evidence, don't assume):
- **Databento** — strong CME futures coverage, historical + live, good schemas.
- **Polygon.io** — broad markets; verify futures depth.
- **CQG / Rithmic** — professional futures data feeds (often via broker).
- **Interactive Brokers** — data + execution if used as a secondary venue.
- The **Topstep execution platform's** own feed for live trading.

**Integration:** `MarketDataProvider` (see doc 5). Adapters normalize every
vendor into our `Bar` domain type and write to `market_bars`. Contract specs are
loaded from `config/contracts.yaml` and seeded into `instruments`.

**Order-flow note:** delta/footprint/volume-profile data is heavier and
vendor-specific. It's deferred to Phase 2+/3 and lives behind an *optional*
extension of the market-data interface so the core system runs without it.

---

## 2. Broker / prop-firm execution (Topstep first)

**What we need**
- Account state (balance, open positions, daily P&L, trailing drawdown).
- **Topstep account rules** encoded as risk parameters (daily loss limit, max
  loss / trailing drawdown, consistency rules, contract limits per account
  size).
- Order placement — **paper/dry-run by default**, live only after explicit human
  promotion, and every live order gated by the Risk Engine and a human
  confirmation.

**Topstep specifics**
- Topstep trades are executed on supported platforms (e.g. platforms exposing
  the **ProjectX / TopstepX**-style API, or Rithmic/CQG-backed connectivity).
  The exact API is confirmed at Phase 6, not assumed now.
- Topstep's Trading Combine / funded-account **rules become Risk Engine config**
  in `config/risk_limits.yaml` and `risk_rule_versions`, so the system refuses
  trades that would breach the evaluation before they're sent.

**Integration:** `ExecutionEngine` (see doc 5). The first adapter is a
`PaperExecutionEngine` (simulated fills against `market_bars`) — this is what
backtesting and early live-shadowing use. A `TopstepExecutionEngine` adapter is
added in Phase 6 behind the identical interface.

**Credentials:** broker API keys come from environment variables / a secrets
manager, documented in `.env.example`. They are **never** committed to the repo.

---

## 3. News / economic calendar

**What we need**
- Scheduled high-impact events: FOMC, CPI, PPI, GDP, employment (NFP/JOLTS),
  Fed speakers, plus event severity and forecast/previous/actual values.
- Enough lead time to open a **blackout window** around high-impact events.

**Candidate providers**
- Trading Economics, Financial Modeling Prep, Econoday-style calendars, or the
  broker's built-in calendar. Evaluate coverage + license terms.

**Integration:** `NewsEngine` (see doc 5). Adapters normalize into `news_events`.
The Decision Framework reads upcoming events to compute `news_risk` and can
suppress/down-weight setups inside high-impact windows.

---

## 4. Internal API layer (our own service)

Exposed by `src/tradingsys/api/` (FastAPI) in Phase 6. Consumed by the Dashboard
and any future clients. Illustrative endpoints:

| Method & path | Purpose |
|---------------|---------|
| `GET /health` | Liveness/readiness |
| `GET /instruments` | Contract specs |
| `GET /market/context?symbol=ES&tf=5m` | Current `MarketContext` |
| `GET /recommendations?account_id=…` | Live recommendation feed (incl. `wait`) |
| `POST /recommendations/{id}/approve` | Human approves → execution (paper/live) |
| `POST /recommendations/{id}/reject` | Human rejects, with reason |
| `GET /risk/status?account_id=…` | Live risk budget: daily loss used, trades left, drawdown |
| `POST /trades` / `PATCH /trades/{id}` | Journal write / close-out |
| `GET /analytics?account_id=…&scope=by_strategy` | Materialized metrics |
| `GET /learning/proposals` / `POST /learning/proposals/{id}/approve` | Human review of learning changes |

**Rules:** the API is a delivery mechanism only — no trading logic. Write
endpoints that can move money (`approve`) require authentication and always pass
through the Risk Engine veto server-side, regardless of what the client sends.

---

## Environment variables (documented in `.env.example`)

```
# --- Database ---
DATABASE_URL=postgresql://user:pass@localhost:5432/tradingsys

# --- Market data vendor (adapter-selected) ---
MARKET_DATA_PROVIDER=databento
MARKET_DATA_API_KEY=__set_in_secrets_manager__

# --- News vendor ---
NEWS_PROVIDER=trading_economics
NEWS_API_KEY=__set_in_secrets_manager__

# --- Broker / execution (Topstep) ---
EXECUTION_MODE=paper            # paper | live  (paper is the default)
BROKER=topstep
BROKER_API_KEY=__set_in_secrets_manager__
BROKER_ACCOUNT_ID=__set__

# --- Runtime ---
ENV=dev                         # dev | staging | prod
```

No real secret ever lives in the repo — `.env.example` documents names only.
