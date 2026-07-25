"""Shared fixtures: an in-memory system wired end-to-end (no external infra)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from tradingsys.domain.types import AccountState, Instrument, RiskRules
from tradingsys.persistence.memory import (
    InMemoryInstrumentRepository,
    InMemoryRecommendationRepository,
    InMemoryRiskRepository,
    InMemoryTradeRepository,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 7, 22, 14, 30, tzinfo=timezone.utc)


@pytest.fixture
def es() -> Instrument:
    return Instrument(
        symbol="ES",
        name="E-mini S&P 500",
        exchange="CME",
        tick_size=Decimal("0.25"),
        tick_value=Decimal("12.50"),
    )


@pytest.fixture
def instruments(es: Instrument) -> InMemoryInstrumentRepository:
    repo = InMemoryInstrumentRepository()
    repo.upsert(es)
    return repo


@pytest.fixture
def trades() -> InMemoryTradeRepository:
    return InMemoryTradeRepository()


@pytest.fixture
def recommendations() -> InMemoryRecommendationRepository:
    return InMemoryRecommendationRepository()


@pytest.fixture
def rules() -> RiskRules:
    return RiskRules(
        version=1,
        max_daily_loss=Decimal("1000"),
        max_drawdown=Decimal("2000"),
        risk_per_trade_pct=Decimal("0.005"),
        max_daily_trades=5,
        max_open_positions=1,
        max_contracts=3,
        max_weekly_loss=Decimal("3000"),
        approved_by="lucas",
        approved_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def risk_repo(rules: RiskRules) -> InMemoryRiskRepository:
    repo = InMemoryRiskRepository()
    repo.seed_active(account_id=1, rules=rules)
    return repo


@pytest.fixture
def flat_account() -> AccountState:
    return AccountState(
        account_id=1,
        balance=Decimal("50000"),
        open_positions=0,
        daily_pnl=Decimal("0"),
        daily_trades=0,
        weekly_pnl=Decimal("0"),
        current_drawdown=Decimal("0"),
        is_paper=True,
    )
