"""CSV historical-data loader — parses real exported bars into the Bar type."""
from __future__ import annotations

from decimal import Decimal

from tradingsys.domain.types import Instrument
from tradingsys.engines.market_data.csv_provider import CsvMarketDataProvider, load_bars_csv

CSV = """Date,Open,High,Low,Close,Volume
2026-06-01 13:30,5000,5002,4999,5001,1200
2026-06-01 13:35,5001,5004,5000,5003,1500
2026-06-01 13:40,5003,5003,4998,4999,900
"""


def _write(tmp_path):
    p = tmp_path / "es.csv"
    p.write_text(CSV)
    return p


def test_load_bars_csv_flexible_headers(tmp_path):
    bars = load_bars_csv(_write(tmp_path), "ES", "5m")
    assert len(bars) == 3
    assert bars[0].open == Decimal("5000") and bars[0].close == Decimal("5001")
    assert bars[0].volume == 1200
    assert bars[0].ts < bars[1].ts < bars[2].ts   # sorted ascending
    assert bars[0].ts.tzinfo is not None          # made tz-aware (UTC)


def test_provider_serves_bars(tmp_path):
    es = Instrument(symbol="ES", name="ES", exchange="CME",
                    tick_size=Decimal("0.25"), tick_value=Decimal("12.50"))
    provider = CsvMarketDataProvider(es, _write(tmp_path), timeframe="5m")
    assert len(provider.all_bars()) == 3
    assert provider.get_instrument_spec("ES").tick_value == Decimal("12.50")
