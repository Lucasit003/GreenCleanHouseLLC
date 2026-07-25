-- =====================================================================
-- Adaptive AI Futures Trading — Canonical Database Schema
-- Target: PostgreSQL 15+  (TimescaleDB optional for market_bars)
--
-- Design notes:
--   * All money stored as NUMERIC (never float) — trading P&L must be exact.
--   * All timestamps are TIMESTAMPTZ, stored in UTC.
--   * "Own data first": trades + setups are the source of truth for analytics.
--   * Every recommendation and risk decision is persisted for auditability.
--   * Core risk rules are versioned and require human approval to change.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Reference data
-- ---------------------------------------------------------------------

-- Tradable futures contracts and their specifications.
CREATE TABLE instruments (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL UNIQUE,          -- e.g. 'ES', 'NQ', 'CL'
    name            TEXT NOT NULL,
    exchange        TEXT NOT NULL,                 -- e.g. 'CME'
    tick_size       NUMERIC(18,8) NOT NULL,        -- min price increment
    tick_value      NUMERIC(18,8) NOT NULL,        -- $ per tick per contract
    currency        TEXT NOT NULL DEFAULT 'USD',
    session_tz      TEXT NOT NULL DEFAULT 'America/New_York',
    rth_open        TIME,                          -- regular trading hours
    rth_close       TIME,
    margin_initial  NUMERIC(18,2),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Market data
-- ---------------------------------------------------------------------

-- OHLCV bars. (Candidate for a TimescaleDB hypertable on ts.)
CREATE TABLE market_bars (
    instrument_id   BIGINT NOT NULL REFERENCES instruments(id),
    timeframe       TEXT NOT NULL,                 -- '1m','5m','15m','1h','1d'
    ts              TIMESTAMPTZ NOT NULL,          -- bar OPEN time, UTC
    open            NUMERIC(18,8) NOT NULL,
    high            NUMERIC(18,8) NOT NULL,
    low             NUMERIC(18,8) NOT NULL,
    close           NUMERIC(18,8) NOT NULL,
    volume          BIGINT NOT NULL DEFAULT 0,
    source          TEXT NOT NULL,                 -- data vendor / feed
    PRIMARY KEY (instrument_id, timeframe, ts)
);
CREATE INDEX idx_market_bars_ts ON market_bars (ts);

-- ---------------------------------------------------------------------
-- Strategies & confidence (evidence-driven, adaptive)
-- ---------------------------------------------------------------------

CREATE TABLE strategies (
    id              BIGSERIAL PRIMARY KEY,
    key             TEXT NOT NULL UNIQUE,          -- 'trend_pullback', 'orb'
    name            TEXT NOT NULL,
    description     TEXT,
    ideal_conditions  JSONB NOT NULL DEFAULT '{}', -- documented, not assumed
    poor_conditions   JSONB NOT NULL DEFAULT '{}',
    is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Confidence is a time series, never a single mutable value. It rises/falls
-- with long-term evidence. History is retained so we can audit the trajectory
-- and detect overfitting.
CREATE TABLE strategy_confidence (
    id              BIGSERIAL PRIMARY KEY,
    strategy_id     BIGINT NOT NULL REFERENCES strategies(id),
    as_of           TIMESTAMPTZ NOT NULL DEFAULT now(),
    confidence      NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    sample_size     INTEGER NOT NULL,              -- trades behind this score
    method          TEXT NOT NULL,                 -- how it was computed
    notes           TEXT,
    UNIQUE (strategy_id, as_of)
);

-- ---------------------------------------------------------------------
-- Risk configuration (SACRED — versioned, human-approved)
-- ---------------------------------------------------------------------

-- Never mutated in place. A change inserts a new version with approver info.
-- The active row is the latest with approved_at NOT NULL and no successor.
CREATE TABLE risk_rule_versions (
    id                  BIGSERIAL PRIMARY KEY,
    version             INTEGER NOT NULL UNIQUE,
    max_daily_loss      NUMERIC(18,2) NOT NULL,     -- account currency
    max_drawdown        NUMERIC(18,2) NOT NULL,
    risk_per_trade_pct  NUMERIC(6,4) NOT NULL,      -- fraction of account/limit
    max_daily_trades    INTEGER NOT NULL,
    max_weekly_loss     NUMERIC(18,2),
    max_open_positions  INTEGER NOT NULL DEFAULT 1,
    max_contracts       INTEGER NOT NULL,
    rules_json          JSONB NOT NULL DEFAULT '{}',-- extra prop-firm rules
    proposed_by         TEXT NOT NULL,              -- 'learning_engine' | user
    approved_by         TEXT,                       -- human approver (required)
    approved_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Accounts (Topstep now; other prop firms later)
-- ---------------------------------------------------------------------

CREATE TABLE accounts (
    id              BIGSERIAL PRIMARY KEY,
    broker          TEXT NOT NULL DEFAULT 'topstep',
    external_id     TEXT,                          -- broker account id
    label           TEXT NOT NULL,
    starting_balance NUMERIC(18,2) NOT NULL,
    is_paper        BOOLEAN NOT NULL DEFAULT TRUE, -- paper by default
    risk_rule_version INTEGER REFERENCES risk_rule_versions(version),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Market context snapshots (explainability inputs)
-- ---------------------------------------------------------------------

CREATE TABLE market_contexts (
    id              BIGSERIAL PRIMARY KEY,
    instrument_id   BIGINT NOT NULL REFERENCES instruments(id),
    ts              TIMESTAMPTZ NOT NULL,
    timeframe       TEXT NOT NULL,
    trend           TEXT,        -- bull|bear|range
    structure       TEXT,        -- accumulation|distribution|breakout|...
    volatility_regime TEXT,      -- low|normal|high (from ATR)
    session         TEXT,        -- asia|london|ny_am|ny_pm
    atr             NUMERIC(18,8),
    key_levels      JSONB NOT NULL DEFAULT '[]',   -- support/resistance
    factors         JSONB NOT NULL DEFAULT '{}',   -- full labeled factor set
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Setups → Recommendations → Risk decisions → Trades
-- (the core decision + audit chain)
-- ---------------------------------------------------------------------

-- A candidate opportunity emitted by a strategy (not yet risk-checked).
CREATE TABLE setups (
    id              BIGSERIAL PRIMARY KEY,
    strategy_id     BIGINT NOT NULL REFERENCES strategies(id),
    instrument_id   BIGINT NOT NULL REFERENCES instruments(id),
    market_context_id BIGINT REFERENCES market_contexts(id),
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    direction       TEXT NOT NULL CHECK (direction IN ('long','short')),
    proposed_entry  NUMERIC(18,8) NOT NULL,
    proposed_stop   NUMERIC(18,8) NOT NULL,
    proposed_target NUMERIC(18,8),
    reward_risk     NUMERIC(10,4),
    rationale       TEXT NOT NULL,                 -- why this setup exists
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The scored, explainable output the trader actually sees. May be 'wait'.
CREATE TABLE recommendations (
    id              BIGSERIAL PRIMARY KEY,
    setup_id        BIGINT REFERENCES setups(id),
    account_id      BIGINT NOT NULL REFERENCES accounts(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    action          TEXT NOT NULL CHECK (action IN ('enter','wait','avoid')),
    direction       TEXT CHECK (direction IN ('long','short')),
    score           NUMERIC(5,4),                  -- 0..1 composite quality
    confidence      NUMERIC(5,4),                  -- strategy confidence used
    suggested_size  INTEGER,                       -- contracts (post risk-sizing)
    entry           NUMERIC(18,8),
    stop            NUMERIC(18,8),
    target          NUMERIC(18,8),
    explanation     JSONB NOT NULL DEFAULT '{}',   -- every factor, labeled
    news_risk       JSONB NOT NULL DEFAULT '{}',
    created_by      TEXT NOT NULL DEFAULT 'decision_framework'
);

-- Every risk evaluation, whether it passed or vetoed. Full audit.
CREATE TABLE risk_decisions (
    id              BIGSERIAL PRIMARY KEY,
    recommendation_id BIGINT REFERENCES recommendations(id),
    account_id      BIGINT NOT NULL REFERENCES accounts(id),
    risk_rule_version INTEGER NOT NULL REFERENCES risk_rule_versions(version),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved        BOOLEAN NOT NULL,
    veto_reasons    JSONB NOT NULL DEFAULT '[]',   -- why rejected, if rejected
    computed_size   INTEGER,
    risk_amount     NUMERIC(18,2),                 -- $ at risk if stopped
    checks          JSONB NOT NULL DEFAULT '{}'    -- each rule + pass/fail
);

-- The trade journal — the heart of the system. One row per executed trade.
CREATE TABLE trades (
    id              BIGSERIAL PRIMARY KEY,
    account_id      BIGINT NOT NULL REFERENCES accounts(id),
    instrument_id   BIGINT NOT NULL REFERENCES instruments(id),
    strategy_id     BIGINT REFERENCES strategies(id),
    setup_id        BIGINT REFERENCES setups(id),
    recommendation_id BIGINT REFERENCES recommendations(id),
    is_paper        BOOLEAN NOT NULL DEFAULT TRUE,
    direction       TEXT NOT NULL CHECK (direction IN ('long','short')),
    quantity        INTEGER NOT NULL,              -- contracts
    entry_time      TIMESTAMPTZ NOT NULL,
    entry_price     NUMERIC(18,8) NOT NULL,
    stop_price      NUMERIC(18,8),
    target_price    NUMERIC(18,8),
    exit_time       TIMESTAMPTZ,
    exit_price      NUMERIC(18,8),
    -- realized numbers (computed at close, stored for fast analytics)
    gross_pnl       NUMERIC(18,2),
    fees            NUMERIC(18,2) DEFAULT 0,
    net_pnl         NUMERIC(18,2),
    risk_amount     NUMERIC(18,2),                 -- planned $ risk at entry
    reward_risk_planned  NUMERIC(10,4),
    r_multiple      NUMERIC(10,4),                 -- realized net_pnl / risk
    result          TEXT CHECK (result IN ('win','loss','breakeven','open')),
    session         TEXT,
    entry_reason    TEXT,
    exit_reason     TEXT,
    mistakes        TEXT,                          -- what went wrong
    lessons         TEXT,                          -- what to improve
    screenshot_url  TEXT,
    tags            TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_trades_account_time ON trades (account_id, entry_time);
CREATE INDEX idx_trades_strategy ON trades (strategy_id);
CREATE INDEX idx_trades_result ON trades (result);

-- Individual fills (a trade may scale in/out across several fills).
CREATE TABLE trade_fills (
    id              BIGSERIAL PRIMARY KEY,
    trade_id        BIGINT NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    ts              TIMESTAMPTZ NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('buy','sell')),
    quantity        INTEGER NOT NULL,
    price           NUMERIC(18,8) NOT NULL,
    fee             NUMERIC(18,2) NOT NULL DEFAULT 0,
    is_entry        BOOLEAN NOT NULL
);

-- ---------------------------------------------------------------------
-- News / economic calendar
-- ---------------------------------------------------------------------

CREATE TABLE news_events (
    id              BIGSERIAL PRIMARY KEY,
    event_time      TIMESTAMPTZ NOT NULL,
    name            TEXT NOT NULL,                 -- 'CPI', 'FOMC', ...
    category        TEXT,                          -- inflation|employment|fed
    severity        TEXT NOT NULL CHECK (severity IN ('low','medium','high')),
    country         TEXT DEFAULT 'US',
    forecast        TEXT,
    previous        TEXT,
    actual          TEXT,
    source          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_time, name, country)
);

-- ---------------------------------------------------------------------
-- Analytics snapshots (materialized results from Statistics Engine)
-- ---------------------------------------------------------------------

CREATE TABLE analytics_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    account_id      BIGINT NOT NULL REFERENCES accounts(id),
    as_of           TIMESTAMPTZ NOT NULL DEFAULT now(),
    scope           TEXT NOT NULL,   -- 'overall'|'by_strategy'|'by_session'|...
    scope_key       TEXT,            -- e.g. strategy key / session / weekday
    sample_size     INTEGER NOT NULL,
    win_rate        NUMERIC(6,4),
    avg_winner      NUMERIC(18,2),
    avg_loser       NUMERIC(18,2),
    expectancy      NUMERIC(18,4),
    profit_factor   NUMERIC(18,4),
    max_drawdown    NUMERIC(18,2),
    sharpe          NUMERIC(10,4),
    avg_hold_min    NUMERIC(10,2),
    metrics         JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_analytics_scope ON analytics_snapshots (account_id, scope, as_of);

-- ---------------------------------------------------------------------
-- Behavioral / psychology observations (Performance Review Engine)
-- ---------------------------------------------------------------------

CREATE TABLE behavior_flags (
    id              BIGSERIAL PRIMARY KEY,
    account_id      BIGINT NOT NULL REFERENCES accounts(id),
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    pattern         TEXT NOT NULL,   -- overtrading|revenge|fomo|plan_deviation
    severity        TEXT NOT NULL CHECK (severity IN ('info','warn','critical')),
    evidence        JSONB NOT NULL DEFAULT '{}',
    recommendation  TEXT
);

-- ---------------------------------------------------------------------
-- Learning proposals (Learning Engine → human approval queue)
-- ---------------------------------------------------------------------

CREATE TABLE learning_proposals (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind            TEXT NOT NULL,   -- 'confidence_update'|'risk_change'|'flag'
    target          TEXT NOT NULL,   -- e.g. strategy key
    payload         JSONB NOT NULL,  -- proposed change + supporting evidence
    evidence_sample INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected','applied')),
    -- risk_change proposals ALWAYS require human approval before applying
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMPTZ
);

COMMIT;
