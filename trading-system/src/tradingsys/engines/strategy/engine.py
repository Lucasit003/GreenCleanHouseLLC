"""Strategy Engine (Step 7) — registry that fans a context out to strategies."""
from __future__ import annotations

from typing import Sequence

from ...domain.types import Bar, MarketContext, Setup
from ...interfaces.strategy import Strategy


class StrategyEngine:
    def __init__(self) -> None:
        self._strategies: list[Strategy] = []

    def register(self, strategy: Strategy) -> None:
        self._strategies.append(strategy)

    def enabled_strategies(self) -> Sequence[Strategy]:
        return list(self._strategies)

    def generate_setups(self, context: MarketContext, bars: Sequence[Bar]) -> Sequence[Setup]:
        setups: list[Setup] = []
        for strat in self._strategies:
            setups.extend(strat.find_setups(context, bars))
        return setups
