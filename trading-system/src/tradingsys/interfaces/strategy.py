"""Strategy contracts.

A ``Strategy`` is a pluggable, self-describing module that emits candidate
``Setup`` objects — never a naked "buy". It declares the conditions in which it
is expected to work and fail (documented, not assumed), so the Decision
Framework and analytics can measure it against those claims.

The ``StrategyEngine`` hosts the registry of enabled strategies and fans a
``MarketContext`` out to each.
"""
from __future__ import annotations

from typing import Mapping, Protocol, Sequence, runtime_checkable

from ..domain.types import Bar, MarketContext, Setup


@runtime_checkable
class Strategy(Protocol):
    key: str            # stable identifier, e.g. 'trend_pullback'
    name: str

    def ideal_conditions(self) -> Mapping[str, object]:
        """Documented conditions under which this strategy is expected to work."""
        ...

    def poor_conditions(self) -> Mapping[str, object]:
        """Documented conditions under which it is expected to fail."""
        ...

    def find_setups(
        self, context: MarketContext, bars: Sequence[Bar]
    ) -> Sequence[Setup]:
        """Emit zero or more candidate setups. Zero is a valid, common answer."""
        ...


@runtime_checkable
class StrategyEngine(Protocol):
    def register(self, strategy: Strategy) -> None: ...
    def enabled_strategies(self) -> Sequence[Strategy]: ...

    def generate_setups(
        self, context: MarketContext, bars: Sequence[Bar]
    ) -> Sequence[Setup]:
        """Collect setups from every enabled strategy for this context."""
        ...
