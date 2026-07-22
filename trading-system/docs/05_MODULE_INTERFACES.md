# Deliverable 5 — Module Interfaces

These are the **contracts between the 12 modules**. They exist as real,
importable Python in [`src/tradingsys/interfaces/`](../src/tradingsys/interfaces/)
(verified to import cleanly). Engines depend on these `Protocol`s, never on each
other's concrete classes — that is what makes every module independently
replaceable.

All types referenced below live in
[`src/tradingsys/domain/types.py`](../src/tradingsys/domain/types.py).

## The 12 modules and their contracts

| Module | Interface file | Contract (Protocol) | One-line responsibility |
|--------|----------------|---------------------|-------------------------|
| Database | `repository.py` | `*Repository` | Storage access; the only place SQL lives |
| Market Data | `market_data.py` | `MarketDataProvider` | Historical + streaming bars, normalized |
| Market Analysis | `market_analysis.py` | `MarketAnalysisEngine` | Bars → labeled `MarketContext` |
| Strategy | `strategy.py` | `Strategy`, `StrategyEngine` | Emit candidate `Setup`s (never a naked buy) |
| Risk Management | `risk.py` | `RiskEngine` | **Hard veto**, sizing, sacred rules |
| Journal | `journal.py` | `JournalEngine` | Record/close/annotate every trade |
| Statistics | `statistics.py` | `StatisticsEngine` | Own-data metrics, sliced by scope |
| News | `news.py` | `NewsEngine` | Economic calendar + news-risk windows |
| Learning | `learning.py` | `LearningEngine` | Evidence-based confidence; proposals only |
| Performance Review | `performance.py` | `PerformanceReviewEngine` | Behavioral/psychology coaching |
| Execution | `execution.py` | `ExecutionEngine` | Broker connectivity; paper-first, human-gated |
| API + Dashboard | *(delivery layer)* | FastAPI + UI | Expose the above; no trading logic |

> The Decision Framework (`src/tradingsys/decision/`) is not a 13th engine — it
> is the **composition point** that wires these interfaces into a single scored,
> explainable recommendation. See below.

## How a recommendation is produced (the composition)

```
                    MarketDataProvider.get_history / stream
                                   │  bars
                                   ▼
                     MarketAnalysisEngine.analyze
                                   │  MarketContext (labeled)
                                   ▼
                     StrategyEngine.generate_setups
                                   │  Setup[]  (each with rationale)
                                   ▼
        ┌───────────── Decision Framework ─────────────┐
        │  for each Setup:                              │
        │    NewsEngine.news_risk(...)   ── news factor │
        │    StatisticsEngine.by_scope(...) ── own-data │
        │    LearningEngine confidence   ── evidence    │
        │    RiskEngine.evaluate(...)    ── HARD VETO ──┼──► if vetoed → action=AVOID
        │    compose score + explanation                │
        └───────────────────┬───────────────────────────┘
                             ▼
                    Recommendation
             (ENTER | WAIT | AVOID, fully explained)
                             │
                 human approves (API/Dashboard)
                             ▼
     ExecutionEngine.submit(rec, risk_decision, human_confirmed=True)
                             │
                             ▼
                 JournalEngine.open_trade  →  … close_trade
                             ▼
   StatisticsEngine / LearningEngine / PerformanceReviewEngine  (feedback loop)
```

Notes on the contract-level guarantees:

- **The Risk Engine's veto is authoritative.** `RiskEngine.evaluate` returns a
  `RiskDecision`; a vetoed decision forces the recommendation to `AVOID`. No
  other module can override it.
- **`WAIT` is a first-class output.** When the composite score/confidence is
  weak or evidence is insufficient, the Decision Framework returns
  `RecommendationAction.WAIT` — patience, not a trade.
- **Execution is double-gated.** `ExecutionEngine.submit` requires *both* an
  approved `RiskDecision` and `human_confirmed=True`, and adapters must raise
  otherwise. Paper is the default (`is_paper == True`).
- **Learning cannot touch risk.** `LearningEngine` returns `LearningProposal`s;
  anything with `kind='risk_change'` carries `requires_human_approval=True` and
  can only be applied through `RiskEngine.approve_rule_change(..., approved_by=<human>)`.
- **Every strategy is self-describing.** `Strategy.ideal_conditions()` /
  `poor_conditions()` document expectations so the Statistics/Learning engines
  can measure claims against reality rather than trusting them.

## Dependency direction (enforced)

```
domain/  ◄── interfaces/  ◄── engines/*  ◄── decision/  ◄── api/, dashboard/
   ▲            ▲
   └── nothing  └── only domain
```

Engines receive their collaborators via constructor injection (an engine is
handed a `RiskEngine`, a `MarketDataProvider`, repositories, …). They import
concrete classes of *no other engine*. Tests substitute in-memory fakes that
satisfy the same Protocols.
