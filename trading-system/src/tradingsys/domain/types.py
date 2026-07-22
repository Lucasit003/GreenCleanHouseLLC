"""Core domain model for the Adaptive AI Futures Trading system.

This module is intentionally dependency-free (standard library only). Every
other package may import it; it imports nothing from the rest of the codebase.
These are the shared vocabulary types that flow across module boundaries.

Nothing here performs I/O or business logic — these are data structures only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class Trend(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    RANGE = "range"


class Structure(str, Enum):
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    BREAKOUT = "breakout"
    FAILED_BREAKOUT = "failed_breakout"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    TREND_CONTINUATION = "trend_continuation"
    TREND_EXHAUSTION = "trend_exhaustion"
    UNKNOWN = "unknown"


class VolatilityRegime(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Session(str, Enum):
    ASIA = "asia"
    LONDON = "london"
    NY_AM = "ny_am"
    NY_PM = "ny_pm"
    OVERNIGHT = "overnight"


class RecommendationAction(str, Enum):
    ENTER = "enter"
    WAIT = "wait"   # the correct answer when evidence is weak
    AVOID = "avoid"


class TradeResult(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"


class NewsSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Reference & market data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Instrument:
    """A tradable futures contract and its specification."""
    symbol: str
    name: str
    exchange: str
    tick_size: Decimal
    tick_value: Decimal          # dollars per tick per contract
    currency: str = "USD"
    session_tz: str = "America/New_York"
    margin_initial: Optional[Decimal] = None
    id: Optional[int] = None


@dataclass(frozen=True)
class Bar:
    """A single OHLCV bar. ``ts`` is the bar OPEN time in UTC."""
    instrument: str              # symbol
    timeframe: str               # '1m','5m','15m','1h','1d'
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    source: str = ""


# ---------------------------------------------------------------------------
# Market analysis output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KeyLevel:
    price: Decimal
    kind: str                    # 'support' | 'resistance' | 'vwap' | ...
    strength: float = 0.0        # 0..1


@dataclass(frozen=True)
class MarketContext:
    """A labeled snapshot of market state — the explainability substrate.

    Every field is a *labeled observation*, so any downstream recommendation can
    cite exactly which conditions produced it.
    """
    instrument: str
    timeframe: str
    ts: datetime
    trend: Trend
    structure: Structure
    volatility_regime: VolatilityRegime
    session: Session
    atr: Optional[Decimal] = None
    key_levels: tuple[KeyLevel, ...] = ()
    factors: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Strategy / setup / recommendation chain
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Setup:
    """A candidate opportunity emitted by a strategy — NOT yet risk-checked."""
    strategy_key: str
    instrument: str
    direction: Direction
    proposed_entry: Decimal
    proposed_stop: Decimal
    proposed_target: Optional[Decimal]
    rationale: str               # why this setup exists — never empty
    detected_at: datetime
    reward_risk: Optional[float] = None
    market_context: Optional[MarketContext] = None
    id: Optional[int] = None


@dataclass(frozen=True)
class Confidence:
    """Evidence-based confidence for a strategy. Never exists without a sample."""
    strategy_key: str
    value: float                 # 0..1
    sample_size: int
    method: str
    as_of: datetime


@dataclass(frozen=True)
class Recommendation:
    """The scored, explainable output the trader sees. May be WAIT/AVOID."""
    action: RecommendationAction
    account_id: int
    created_at: datetime
    setup: Optional[Setup] = None
    direction: Optional[Direction] = None
    score: Optional[float] = None            # 0..1 composite quality
    confidence: Optional[float] = None       # strategy confidence used
    suggested_size: Optional[int] = None     # contracts, post risk-sizing
    entry: Optional[Decimal] = None
    stop: Optional[Decimal] = None
    target: Optional[Decimal] = None
    explanation: dict[str, Any] = field(default_factory=dict)  # every factor
    news_risk: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskRules:
    """The SACRED risk configuration. Versioned; changed only with human sign-off."""
    version: int
    max_daily_loss: Decimal
    max_drawdown: Decimal
    risk_per_trade_pct: Decimal
    max_daily_trades: int
    max_open_positions: int
    max_contracts: int
    max_weekly_loss: Optional[Decimal] = None
    extra: dict[str, Any] = field(default_factory=dict)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


@dataclass(frozen=True)
class RiskDecision:
    """The result of a risk evaluation — records both approvals and vetoes."""
    approved: bool
    risk_rule_version: int
    checks: dict[str, bool]                  # each rule -> pass/fail
    veto_reasons: tuple[str, ...] = ()
    computed_size: Optional[int] = None
    risk_amount: Optional[Decimal] = None


@dataclass(frozen=True)
class AccountState:
    """Live account snapshot the Risk Engine needs to make a decision."""
    account_id: int
    balance: Decimal
    open_positions: int
    daily_pnl: Decimal
    daily_trades: int
    weekly_pnl: Decimal
    current_drawdown: Decimal
    is_paper: bool = True


# ---------------------------------------------------------------------------
# Journal / trades
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    """One executed trade — the heart of the journal. Mutable: closed later."""
    account_id: int
    instrument: str
    direction: Direction
    quantity: int
    entry_time: datetime
    entry_price: Decimal
    is_paper: bool = True
    stop_price: Optional[Decimal] = None
    target_price: Optional[Decimal] = None
    strategy_key: Optional[str] = None
    setup_id: Optional[int] = None
    recommendation_id: Optional[int] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[Decimal] = None
    net_pnl: Optional[Decimal] = None
    risk_amount: Optional[Decimal] = None
    r_multiple: Optional[float] = None
    result: TradeResult = TradeResult.OPEN
    session: Optional[Session] = None
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None
    mistakes: Optional[str] = None
    lessons: Optional[str] = None
    screenshot_url: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    id: Optional[int] = None


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NewsEvent:
    event_time: datetime
    name: str
    severity: NewsSeverity
    category: Optional[str] = None
    country: str = "US"
    forecast: Optional[str] = None
    previous: Optional[str] = None
    actual: Optional[str] = None
    source: str = ""


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PerformanceMetrics:
    """Computed from the trader's OWN journal — not internet win rates."""
    scope: str                   # 'overall'|'by_strategy'|'by_session'|...
    scope_key: Optional[str]
    sample_size: int
    win_rate: Optional[float] = None
    avg_winner: Optional[Decimal] = None
    avg_loser: Optional[Decimal] = None
    expectancy: Optional[Decimal] = None
    profit_factor: Optional[float] = None
    max_drawdown: Optional[Decimal] = None
    sharpe: Optional[float] = None
    avg_hold_min: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BehaviorFlag:
    """A detected psychology/behavior pattern with a corrective suggestion."""
    account_id: int
    detected_at: datetime
    pattern: str                 # overtrading|revenge|fomo|plan_deviation
    severity: str                # info|warn|critical
    evidence: dict[str, Any] = field(default_factory=dict)
    recommendation: Optional[str] = None


@dataclass(frozen=True)
class LearningProposal:
    """A change the Learning Engine proposes. Risk changes need human approval."""
    kind: str                    # 'confidence_update'|'risk_change'|'flag'
    target: str
    payload: dict[str, Any]
    evidence_sample: int
    created_at: datetime
    requires_human_approval: bool = True
