"""CSV historical data provider (Step 5, real-data path).

Loads REAL historical bars from a CSV you supply (export from Webull,
TradingView, NinjaTrader, or any free data source) and serves them behind the
same ``MarketDataProvider`` contract as everything else — so the backtester and
Combine simulator run on real market history with no other changes.

Accepted columns (case-insensitive, flexible names):
  time/timestamp/datetime/date, open, high, low, close, volume
Datetime is parsed from ISO-8601 or common formats; if only a date is present it
is used as-is (UTC).
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator, Optional, Sequence

from ...domain.types import Bar, Instrument

_TIME_KEYS = ("timestamp", "datetime", "time", "date")
_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M", "%m/%d/%Y", "%Y-%m-%d",
)


def _parse_ts(raw: str) -> datetime:
    raw = raw.strip()
    if raw.isdigit():  # epoch seconds or ms
        val = int(raw)
        if val > 10_000_000_000:
            val //= 1000
        return datetime.fromtimestamp(val, tz=timezone.utc)
    for fmt in _FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"unrecognized datetime: {raw!r}")


def load_bars_csv(path: str | Path, symbol: str, timeframe: str) -> list[Bar]:
    rows: list[Bar] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        lower = {name.lower(): name for name in (reader.fieldnames or [])}
        tkey = next((lower[k] for k in _TIME_KEYS if k in lower), None)
        if tkey is None:
            raise ValueError(f"no time column found in {path}; headers={reader.fieldnames}")

        def col(row, *names):
            for n in names:
                if n in lower:
                    return row[lower[n]]
            raise ValueError(f"missing column any of {names}")

        for row in reader:
            if not row.get(tkey):
                continue
            rows.append(Bar(
                instrument=symbol, timeframe=timeframe, ts=_parse_ts(row[tkey]),
                open=Decimal(str(col(row, "open"))), high=Decimal(str(col(row, "high"))),
                low=Decimal(str(col(row, "low"))), close=Decimal(str(col(row, "close"))),
                volume=int(float(col(row, "volume", "vol") or 0)), source="csv",
            ))
    rows.sort(key=lambda b: b.ts)
    return rows


class CsvMarketDataProvider:
    def __init__(self, instrument: Instrument, path: str | Path, timeframe: str = "5m") -> None:
        self._instrument = instrument
        self._bars = load_bars_csv(path, instrument.symbol, timeframe)

    def get_instrument_spec(self, symbol: str) -> Instrument:
        return self._instrument

    def get_history(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> Sequence[Bar]:
        return [b for b in self._bars if start <= b.ts <= end]

    def all_bars(self) -> Sequence[Bar]:
        return list(self._bars)

    def stream(self, symbol: str, timeframe: str) -> Iterator[Bar]:
        yield from self._bars
