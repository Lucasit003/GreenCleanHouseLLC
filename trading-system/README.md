# Adaptive AI Futures Trading — Research & Decision Support System

A modular, evidence-driven platform that helps a human trader identify
high-quality futures opportunities on **Topstep** while enforcing strict,
professional risk management.

This system is **decision support**, not an autopilot. It analyzes, scores,
journals, measures, and learns. A human approves every trade and every change
to capital-preservation rules.

---

## Non-negotiable principles

1. **Human-in-the-loop.** The system recommends; the trader decides. No live
   order is ever sent without explicit human confirmation.
2. **Risk rules are sacred.** Core risk-management parameters (max daily loss,
   max drawdown, risk per trade, daily trade limit) can never be changed
   automatically by the Learning Engine. Human approval is required, and every
   change is version-stamped and audited.
3. **Evidence over opinion.** Every strategy carries a confidence score derived
   from measured performance, not internet win rates or intuition. Confidence
   rises and falls with long-term evidence, guarded against overfitting.
4. **Explainability.** Every recommendation ships with the factors that produced
   it (trend, structure, liquidity, volatility, news risk, R:R, historical
   performance of similar setups, current confidence). No black-box "buy" calls.
5. **Uncertainty is a valid output.** When evidence is weak, the correct
   recommendation is *patience*, not a trade.
6. **Own data first.** Analytics prefer the trader's own realized performance
   over any external benchmark whenever sufficient sample size exists.

> ⚠️ **Not financial advice.** This is a research and journaling tool for a
> single professional trader. It executes nothing without human confirmation and
> makes no guarantees of profit. Trading futures involves substantial risk of
> loss.

---

## Where to start

Read the design docs in order — the system was specified before any module was
built, on purpose:

| # | Doc | What it answers |
|---|-----|-----------------|
| 1 | [docs/01_ROADMAP.md](docs/01_ROADMAP.md) | Milestones, phases, and definition of done |
| 2 | [docs/02_FOLDER_STRUCTURE.md](docs/02_FOLDER_STRUCTURE.md) | Where every kind of code lives and why |
| 3 | [docs/03_DATABASE_SCHEMA.md](docs/03_DATABASE_SCHEMA.md) | Tables, relationships, and the physical `schema.sql` |
| 4 | [docs/04_DATA_SOURCES_AND_APIS.md](docs/04_DATA_SOURCES_AND_APIS.md) | Market data, news, and broker/prop-firm integration |
| 5 | [docs/05_MODULE_INTERFACES.md](docs/05_MODULE_INTERFACES.md) | The contracts between the 12 engines |
| 6 | [docs/06_IMPLEMENTATION_ORDER.md](docs/06_IMPLEMENTATION_ORDER.md) | The exact build sequence, one tested module at a time |
| 7 | [docs/07_AUTONOMOUS_TRADING.md](docs/07_AUTONOMOUS_TRADING.md) | **Trading without a per-trade click** — how, and its hard limits |

Architecture decisions are logged in [docs/adr/](docs/adr/).

## Current status

**Phase 0 — Architecture:** complete (deliverables 1–6).

**Complete for paper practice** — every engine except the live Topstep adapter
is built and covered by a passing test suite (`python -m pytest`, 30 tests, no
external infra needed):

- **Storage (1)** — in-memory repositories satisfying the `interfaces/` contracts
  (Postgres impls behind the same Protocols come later).
- **Journal (2)** — open/close/annotate with exact futures P&L + R-multiple.
- **Statistics v1 & v2 (3, 12)** — win rate, expectancy, profit factor, drawdown,
  Sharpe, sliced by strategy/session/time — from the trader's own journal.
- **Market Data (5)** — deterministic synthetic provider for offline practice,
  behind the same `MarketDataProvider` a live feed will use.
- **Indicators + Market Analysis (6)** — EMA/SMA/ATR/RSI/VWAP and labeled
  `MarketContext` (trend/structure/volatility/session/levels).
- **Strategy (7)** — registry + two strategies (trend pullback, breakout), each
  declaring its ideal/poor conditions.
- **Backtester (8)** — replays bars through the same pipeline and journals them.
- **Risk Engine (9)** — position sizing + authoritative veto.
- **Decision Framework (10)** — composes context + confidence + news + risk into
  a scored, explainable ENTER / WAIT / AVOID.
- **News (11)** — economic-calendar blackout windows.
- **Learning (12)** — overfitting-guarded confidence; proposals only, never
  touches risk.
- **Performance Review (13)** — overtrading / revenge-trade detection.
- **Paper Execution + Autopilot** — trades **without a per-trade click**, paper
  by default, behind a human-armed policy and the Risk veto. See
  **[docs/07](docs/07_AUTONOMOUS_TRADING.md)**.

- **Topstep Combine simulation** — make fake trades under the prop firm's real
  rules (trailing max loss, daily loss limit, profit target, min days, contract
  cap) and get a pass/fail evaluation report. See
  **[docs/08](docs/08_TOPSTEP_SIMULATION.md)**.

**Try it:**
- `python scripts/paper_demo.py` — full pipeline on synthetic data → practice report.
- `python scripts/topstep_sim.py` — run a Topstep Combine under its rules and see
  if the simulated trades pass or fail.

Both are simulations — no account, no live orders.

**Not built (deliberate):** Step 15, the live Topstep adapter, and the web
API/Dashboard v2. Live trading stays off until you decide to open an account.

> ⚠️ **Autonomous live trading is OFF by default and gated.** Read
> [docs/07_AUTONOMOUS_TRADING.md](docs/07_AUTONOMOUS_TRADING.md) — especially the
> requirement to verify Topstep's automation rules — before enabling `live`.
