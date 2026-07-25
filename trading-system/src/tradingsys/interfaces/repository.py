"""Database access contracts (the Repository pattern).

Engines never touch SQL directly — they depend on these Protocols. Concrete
implementations live in ``tradingsys/persistence`` (Phase 1). This is what lets
us swap the storage layer or run engines against an in-memory fake in tests.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence, runtime_checkable

from ..domain.types import (
    Bar,
    Instrument,
    MarketContext,
    NewsEvent,
    Recommendation,
    RiskDecision,
    RiskRules,
    Setup,
    Trade,
)


@runtime_checkable
class InstrumentRepository(Protocol):
    def get(self, symbol: str) -> Optional[Instrument]: ...
    def list_active(self) -> Sequence[Instrument]: ...
    def upsert(self, instrument: Instrument) -> Instrument: ...


@runtime_checkable
class BarRepository(Protocol):
    def get_range(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> Sequence[Bar]: ...
    def latest(self, symbol: str, timeframe: str, n: int = 1) -> Sequence[Bar]: ...
    def bulk_insert(self, bars: Sequence[Bar]) -> int: ...


@runtime_checkable
class TradeRepository(Protocol):
    def add(self, trade: Trade) -> Trade: ...
    def update(self, trade: Trade) -> Trade: ...
    def get(self, trade_id: int) -> Optional[Trade]: ...
    def query(
        self,
        account_id: int,
        *,
        strategy_key: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Sequence[Trade]: ...


@runtime_checkable
class SetupRepository(Protocol):
    def add(self, setup: Setup) -> Setup: ...
    def get(self, setup_id: int) -> Optional[Setup]: ...


@runtime_checkable
class RecommendationRepository(Protocol):
    def add(self, rec: Recommendation) -> Recommendation: ...
    def get(self, rec_id: int) -> Optional[Recommendation]: ...
    def feed(self, account_id: int, limit: int = 50) -> Sequence[Recommendation]: ...


@runtime_checkable
class RiskRepository(Protocol):
    def active_rules(self, account_id: int) -> RiskRules: ...
    def record_decision(
        self, recommendation_id: Optional[int], account_id: int, decision: RiskDecision
    ) -> None: ...
    def propose_new_rules(self, rules: RiskRules, proposed_by: str) -> int: ...
    def approve_rules(self, version: int, approved_by: str) -> None: ...


@runtime_checkable
class MarketContextRepository(Protocol):
    def add(self, ctx: MarketContext) -> int: ...
    def latest(self, symbol: str, timeframe: str) -> Optional[MarketContext]: ...


@runtime_checkable
class NewsRepository(Protocol):
    def upcoming(self, within_minutes: int) -> Sequence[NewsEvent]: ...
    def bulk_upsert(self, events: Sequence[NewsEvent]) -> int: ...
