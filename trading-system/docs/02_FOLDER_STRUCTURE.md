# Deliverable 2 — Folder Structure

The layout follows a **modular monolith**: one deployable process, but strict
internal boundaries. Each engine lives in its own package and may only talk to
another engine through the interfaces in `src/tradingsys/interfaces/`. This keeps
modules "independent and replaceable" (per the brief) without the operational
cost of microservices on day one.

```
trading-system/
├── README.md
├── pyproject.toml                 # deps, tooling, package metadata
├── .env.example                   # documents required env vars (no secrets)
│
├── docs/
│   ├── 01_ROADMAP.md
│   ├── 02_FOLDER_STRUCTURE.md
│   ├── 03_DATABASE_SCHEMA.md
│   ├── 04_DATA_SOURCES_AND_APIS.md
│   ├── 05_MODULE_INTERFACES.md
│   ├── 06_IMPLEMENTATION_ORDER.md
│   └── adr/                       # Architecture Decision Records
│
├── db/
│   ├── schema.sql                 # canonical schema (source of truth for docs)
│   └── migrations/                # versioned migrations (added in Phase 1)
│
├── config/
│   ├── contracts.yaml             # tick size/value, sessions, margins per symbol
│   ├── risk_limits.yaml           # Topstep account rules & risk caps
│   └── settings.yaml              # environment/runtime settings
│
├── src/
│   └── tradingsys/
│       ├── __init__.py
│       ├── config.py              # typed config loading & validation
│       │
│       ├── domain/                # pure data model — no I/O, no engine logic
│       │   ├── __init__.py
│       │   └── types.py           # dataclasses & enums shared by every module
│       │
│       ├── interfaces/            # the contracts (Protocols/ABCs) — Deliverable 5
│       │   ├── __init__.py
│       │   ├── repository.py      # Database access contracts
│       │   ├── market_data.py     # MarketDataProvider
│       │   ├── market_analysis.py # MarketAnalysisEngine
│       │   ├── strategy.py        # Strategy + StrategyEngine
│       │   ├── risk.py            # RiskEngine
│       │   ├── journal.py         # JournalEngine
│       │   ├── statistics.py      # StatisticsEngine
│       │   ├── news.py            # NewsEngine
│       │   ├── learning.py        # LearningEngine
│       │   ├── performance.py     # PerformanceReviewEngine
│       │   └── execution.py       # ExecutionEngine
│       │
│       ├── engines/               # concrete implementations (built in phases)
│       │   ├── __init__.py
│       │   ├── market_data/
│       │   ├── market_analysis/
│       │   ├── strategy/
│       │   │   └── strategies/    # one file per pluggable strategy
│       │   ├── risk/
│       │   ├── journal/
│       │   ├── statistics/
│       │   ├── news/
│       │   ├── learning/
│       │   ├── performance/
│       │   └── execution/
│       │
│       ├── indicators/            # pure indicator functions (EMA, VWAP, ATR…)
│       │
│       ├── decision/              # Decision Framework — composes the engines
│       │   └── framework.py
│       │
│       ├── backtest/              # replay harness (Phase 3)
│       │
│       ├── persistence/           # concrete repository impls (SQL) — Phase 1
│       │
│       ├── api/                   # API Layer (FastAPI) — Phase 6
│       │
│       └── dashboard/             # Dashboard UI — Phases 1 (v1) & 6 (v2)
│
├── tests/
│   ├── unit/                      # mirrors src/ package layout
│   ├── integration/               # module-to-module against real DB
│   └── backtests/                 # reproducible strategy backtests
│
└── scripts/                       # one-off operational scripts (migrate, seed…)
```

## Rules that keep the boundaries honest

1. **`domain/` depends on nothing.** Pure types. Every other package may import
   it; it imports no other package.
2. **`interfaces/` depends only on `domain/`.** They are contracts, not code.
3. **`engines/*` depend on `interfaces/` and `domain/` — never on each other
   directly.** The Strategy Engine does not import the Risk Engine; it receives
   a `RiskEngine` through its constructor. This is what makes a module
   replaceable.
4. **`decision/` is the only place engines are composed.** It wires concrete
   engines together behind the Decision Framework.
5. **`api/` and `dashboard/` are delivery mechanisms.** They call `decision/` and
   the engines through interfaces; they contain no trading logic.
6. **Config and secrets are separate.** `config/*.yaml` holds non-secret,
   version-controlled settings. Secrets (broker keys) come from environment /
   secrets manager, documented in `.env.example`, **never committed**.

## Why a modular monolith (not microservices)

- Single trader, single process — network hops add latency and failure modes
  with no benefit.
- Interfaces already isolate modules, so extraction to services later (if a
  reason ever appears) is mechanical, not a rewrite.
- Backtests and live share the exact same code paths behind the same interfaces,
  which is essential for trustworthy results.

See `docs/adr/0002-python-and-modular-monolith.md`.
