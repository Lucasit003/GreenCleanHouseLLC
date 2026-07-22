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

Architecture decisions are logged in [docs/adr/](docs/adr/).

## Current status

**Phase 0 — Architecture.** Deliverables 1–6 above are complete. The `src/`
tree contains the domain model (`domain/types.py`) and the module interface
contracts (`interfaces/`) — real, importable Python with **no engine
implementations yet**. That is deliberate: implementation begins one tested
module at a time, in the order given in doc 6, starting with the Database +
Journal Engine.
