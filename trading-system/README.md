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

**Implementation in progress** — the following modules are built and covered by a
passing test suite (`python -m pytest`, 15 tests, no external infra needed):

- **Step 1 — Storage:** in-memory repositories satisfying the `interfaces/`
  contracts (Postgres implementations behind the same Protocols come next).
- **Step 2 — Journal Engine:** open/close/annotate with exact futures P&L and
  R-multiple math.
- **Step 3 — Statistics Engine v1:** win rate, expectancy, profit factor,
  drawdown, and per-strategy/session/time slices from the trader's own journal.
- **Risk Engine** (pulled forward from Step 9): position sizing + authoritative
  veto — required before autonomy.
- **Paper Execution Engine + Autopilot:** the system can trade **without a
  per-trade human click**, in paper by default, behind a human-armed policy and
  the Risk Engine veto. See **[docs/07](docs/07_AUTONOMOUS_TRADING.md)**.

The remaining engines (Market Data/Analysis, Strategy, Decision Framework, News,
Learning, Performance Review, live Topstep adapter) follow the order in doc 6.

> ⚠️ **Autonomous live trading is OFF by default and gated.** Read
> [docs/07_AUTONOMOUS_TRADING.md](docs/07_AUTONOMOUS_TRADING.md) — especially the
> requirement to verify Topstep's automation rules — before enabling `live`.
