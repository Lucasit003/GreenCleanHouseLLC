"""In-memory repository implementations (Step 1).

These satisfy the ``interfaces/repository.py`` Protocols with plain dicts. They
exist for two reasons the architecture explicitly calls for:

1. Tests substitute in-memory fakes that satisfy the same contracts.
2. The whole system can run end-to-end (incl. autonomous paper trading) with
   zero external infrastructure while the Postgres-backed implementations
   (``db/schema.sql``) are built out.

The production SQL implementations will live alongside these under
``persistence/`` and expose the identical Protocols, so engines never change.
"""
from __future__ import annotations

from datetime import datetime
from itertools import count
from typing import Optional, Sequence

from ..domain.types import (
    Bar,
    Instrument,
    NewsEvent,
    Recommendation,
    RiskDecision,
    RiskRules,
    Setup,
    Trade,
)


class InMemoryInstrumentRepository:
    def __init__(self) -> None:
        self._by_symbol: dict[str, Instrument] = {}
        self._ids = count(1)

    def get(self, symbol: str) -> Optional[Instrument]:
        return self._by_symbol.get(symbol)

    def list_active(self) -> Sequence[Instrument]:
        return list(self._by_symbol.values())

    def upsert(self, instrument: Instrument) -> Instrument:
        if instrument.id is None:
            instrument = Instrument(**{**instrument.__dict__, "id": next(self._ids)})
        self._by_symbol[instrument.symbol] = instrument
        return instrument


class InMemoryBarRepository:
    def __init__(self) -> None:
        self._bars: list[Bar] = []

    def get_range(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> Sequence[Bar]:
        return [
            b for b in self._bars
            if b.instrument == symbol and b.timeframe == timeframe and start <= b.ts <= end
        ]

    def latest(self, symbol: str, timeframe: str, n: int = 1) -> Sequence[Bar]:
        rows = [b for b in self._bars if b.instrument == symbol and b.timeframe == timeframe]
        return sorted(rows, key=lambda b: b.ts)[-n:]

    def bulk_insert(self, bars: Sequence[Bar]) -> int:
        self._bars.extend(bars)
        return len(bars)


class InMemoryTradeRepository:
    def __init__(self) -> None:
        self._trades: dict[int, Trade] = {}
        self._ids = count(1)

    def add(self, trade: Trade) -> Trade:
        if trade.id is None:
            trade.id = next(self._ids)
        self._trades[trade.id] = trade
        return trade

    def update(self, trade: Trade) -> Trade:
        assert trade.id is not None
        self._trades[trade.id] = trade
        return trade

    def get(self, trade_id: int) -> Optional[Trade]:
        return self._trades.get(trade_id)

    def query(
        self,
        account_id: int,
        *,
        strategy_key: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Sequence[Trade]:
        out = []
        for t in self._trades.values():
            if t.account_id != account_id:
                continue
            if strategy_key is not None and t.strategy_key != strategy_key:
                continue
            if start is not None and t.entry_time < start:
                continue
            if end is not None and t.entry_time > end:
                continue
            out.append(t)
        return sorted(out, key=lambda t: t.entry_time)


class InMemorySetupRepository:
    def __init__(self) -> None:
        self._setups: dict[int, Setup] = {}
        self._ids = count(1)

    def add(self, setup: Setup) -> Setup:
        if setup.id is None:
            setup = Setup(**{**setup.__dict__, "id": next(self._ids)})
        assert setup.id is not None
        self._setups[setup.id] = setup
        return setup

    def get(self, setup_id: int) -> Optional[Setup]:
        return self._setups.get(setup_id)


class InMemoryRecommendationRepository:
    def __init__(self) -> None:
        self._recs: dict[int, Recommendation] = {}
        self._ids = count(1)

    def add(self, rec: Recommendation) -> Recommendation:
        if rec.id is None:
            rec = Recommendation(**{**rec.__dict__, "id": next(self._ids)})
        assert rec.id is not None
        self._recs[rec.id] = rec
        return rec

    def get(self, rec_id: int) -> Optional[Recommendation]:
        return self._recs.get(rec_id)

    def feed(self, account_id: int, limit: int = 50) -> Sequence[Recommendation]:
        rows = [r for r in self._recs.values() if r.account_id == account_id]
        return sorted(rows, key=lambda r: r.created_at, reverse=True)[:limit]


class InMemoryRiskRepository:
    """Enforces the sacred-rule invariant: rule changes are versioned and a
    proposal can only become active via an explicit human ``approve``."""

    def __init__(self) -> None:
        self._versions: dict[int, RiskRules] = {}
        self._active: dict[int, int] = {}  # account_id -> version
        self._decisions: list[tuple[Optional[int], int, RiskDecision]] = []

    def seed_active(self, account_id: int, rules: RiskRules) -> None:
        self._versions[rules.version] = rules
        self._active[account_id] = rules.version

    def active_rules(self, account_id: int) -> RiskRules:
        return self._versions[self._active[account_id]]

    def record_decision(
        self, recommendation_id: Optional[int], account_id: int, decision: RiskDecision
    ) -> None:
        self._decisions.append((recommendation_id, account_id, decision))

    def decisions(self) -> Sequence[tuple[Optional[int], int, RiskDecision]]:
        return list(self._decisions)

    def propose_new_rules(self, rules: RiskRules, proposed_by: str) -> int:
        # A proposal is stored but NEVER activated here — approval is separate.
        self._versions[rules.version] = rules
        return rules.version

    def approve_rules(self, version: int, approved_by: str) -> RiskRules:
        rules = self._versions[version]
        if not approved_by:
            raise ValueError("risk rule approval requires a human approver")
        approved = RiskRules(
            **{**rules.__dict__, "approved_by": approved_by, "approved_at": datetime.utcnow()}
        )
        self._versions[version] = approved
        return approved


class InMemoryNewsRepository:
    def __init__(self) -> None:
        self._events: list[NewsEvent] = []

    def upcoming(self, within_minutes: int) -> Sequence[NewsEvent]:
        now = datetime.utcnow()
        return sorted(
            (e for e in self._events if 0 <= (e.event_time - now).total_seconds() <= within_minutes * 60),
            key=lambda e: e.event_time,
        )

    def bulk_upsert(self, events: Sequence[NewsEvent]) -> int:
        self._events.extend(events)
        return len(events)
