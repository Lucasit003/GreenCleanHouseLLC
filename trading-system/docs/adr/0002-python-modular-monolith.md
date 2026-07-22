# ADR 0002 — Python + modular monolith, interface-first

## Status
Accepted

## Context
The brief demands modules that are "independent and replaceable", strict risk
controls, reproducible backtests, and continuous, evidence-based learning. The
operation is a single trader on Topstep. We must choose a language, a deployment
shape, and a module-boundary strategy.

## Decision
1. **Language: Python 3.11+.** It is the lingua franca of quantitative research
   and data science (pandas/numpy ecosystem), which is where most of this
   system's work lives. Latency needs are modest (decision support, not HFT).
2. **Shape: a modular monolith.** One deployable process, with strict internal
   boundaries — not microservices. A single trader does not benefit from network
   hops between engines.
3. **Interface-first.** Every module hides behind a `Protocol` in
   `interfaces/`. Engines receive collaborators by constructor injection and
   never import each other's concrete classes.
4. **Backtest and live share code paths** behind the same interfaces (e.g. a
   `PaperExecutionEngine` and a `TopstepExecutionEngine` implement one
   `ExecutionEngine`), so backtested behavior reflects live behavior.

## Consequences
- Modules are genuinely replaceable and independently testable (fakes satisfy
  the same Protocols). Extraction to separate services later is mechanical if a
  real need arises.
- Risk controls can be enforced at a single, well-defined boundary that nothing
  bypasses.
- Some Python performance ceilings exist; acceptable for decision support and
  addressable per-hotspot later (vectorization, native extensions) without
  changing the architecture.
- A different frontend stack may be chosen for the Dashboard; it consumes the API
  and is not bound to this decision.
