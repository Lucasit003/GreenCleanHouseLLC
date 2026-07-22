"""Step 6 tests: indicator math and market analysis labeling."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tradingsys.domain.types import Bar, Trend
from tradingsys.engines.market_analysis.engine import MarketAnalysisEngine, session_for
from tradingsys.indicators import atr, ema, rsi, sma


def test_sma_basic():
    out = sma([1, 2, 3, 4], 2)
    assert math.isnan(out[0])
    assert out[1:] == [1.5, 2.5, 3.5]


def test_ema_of_constant_is_constant():
    out = ema([5, 5, 5, 5, 5], 3)
    assert out[-1] == 5.0


def test_atr_constant_range():
    highs = [10, 11, 12, 13, 14]
    lows = [9, 10, 11, 12, 13]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5]
    out = atr(highs, lows, closes, 2)
    assert round(out[-1], 4) == 1.5


def test_rsi_all_gains_is_100():
    out = rsi([1, 2, 3, 4, 5, 6], 2)
    assert out[-1] == 100.0


def test_session_mapping():
    assert session_for(14).value == "ny_am"
    assert session_for(3).value == "asia"


def _uptrend_bars(n=40):
    start = datetime(2026, 7, 1, 14, 0, tzinfo=timezone.utc)
    bars = []
    price = 5000.0
    for i in range(n):
        price += 2.0
        o = Decimal(str(price - 1))
        c = Decimal(str(price))
        bars.append(Bar(
            instrument="ES", timeframe="5m", ts=start + timedelta(minutes=5 * i),
            open=o, high=c + 1, low=o - 1, close=c, volume=1000, source="test",
        ))
    return bars


def test_analysis_detects_uptrend():
    ctx = MarketAnalysisEngine().analyze("ES", "5m", _uptrend_bars())
    assert ctx.trend is Trend.BULL
    assert ctx.atr is not None
    assert ctx.session.value in ("ny_am", "ny_pm")
