"""Synthetic market data provider (Step 5).

A deterministic, seeded bar generator so the whole system can be practiced and
backtested OFFLINE — no vendor, no API key, reproducible results. It implements
the same ``MarketDataProvider`` contract a live vendor adapter will, so nothing
downstream changes when a real feed is plugged in.

It can produce trending or ranging regimes on demand, which is exactly what you
want for practice: see how the strategies and risk controls behave in each.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterator, Sequence

from ...domain.types import Bar, Instrument

_TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}


class SyntheticMarketDataProvider:
    def __init__(
        self,
        instrument: Instrument,
        *,
        seed: int = 42,
        start_price: float = 5000.0,
        drift: float = 0.0,        # per-bar bias; >0 uptrend, <0 downtrend
        volatility: float = 1.5,   # per-bar stddev in price points
    ) -> None:
        self._instrument = instrument
        self._seed = seed
        self._start_price = start_price
        self._drift = drift
        self._vol = volatility

    def get_instrument_spec(self, symbol: str) -> Instrument:
        return self._instrument

    def _snap(self, price: float) -> Decimal:
        tick = float(self._instrument.tick_size)
        return Decimal(str(round(round(price / tick) * tick, 8)))

    def get_history(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> Sequence[Bar]:
        step = timedelta(minutes=_TF_MINUTES[timeframe])
        rng = random.Random(self._seed)
        bars: list[Bar] = []
        price = self._start_price
        ts = start
        while ts <= end:
            o = price
            move = self._drift + rng.gauss(0, self._vol)
            c = o + move
            hi = max(o, c) + abs(rng.gauss(0, self._vol / 2))
            lo = min(o, c) - abs(rng.gauss(0, self._vol / 2))
            vol = int(1000 + abs(rng.gauss(0, 300)))
            bars.append(Bar(
                instrument=symbol, timeframe=timeframe, ts=ts,
                open=self._snap(o), high=self._snap(hi), low=self._snap(lo),
                close=self._snap(c), volume=vol, source="synthetic",
            ))
            price = c
            ts += step
        return bars

    def stream(self, symbol: str, timeframe: str) -> Iterator[Bar]:
        """Yield freshly generated bars indefinitely (for practice loops)."""
        step = timedelta(minutes=_TF_MINUTES[timeframe])
        rng = random.Random(self._seed)
        price = self._start_price
        ts = datetime.now(timezone.utc)
        while True:
            o = price
            c = o + self._drift + rng.gauss(0, self._vol)
            hi = max(o, c) + abs(rng.gauss(0, self._vol / 2))
            lo = min(o, c) - abs(rng.gauss(0, self._vol / 2))
            yield Bar(
                instrument=symbol, timeframe=timeframe, ts=ts,
                open=self._snap(o), high=self._snap(hi), low=self._snap(lo),
                close=self._snap(c), volume=1000, source="synthetic",
            )
            price = c
            ts += step
