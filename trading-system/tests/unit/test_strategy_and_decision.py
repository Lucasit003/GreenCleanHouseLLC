"""Step 7 + Step 10 tests: strategy emission and the decision framework."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tradingsys.decision.framework import DecisionFramework
from tradingsys.domain.types import (
    Bar,
    Direction,
    MarketContext,
    NewsEvent,
    NewsSeverity,
    RecommendationAction,
    Session,
    Setup,
    Structure,
    Trend,
    VolatilityRegime,
)
from tradingsys.engines.learning.engine import LearningEngine
from tradingsys.engines.news.engine import NewsEngine
from tradingsys.engines.risk.engine import RiskEngine
from tradingsys.engines.strategy.strategies.breakout import BreakoutStrategy
from tradingsys.persistence.memory import InMemoryNewsRepository


def _breakout_bars(now):
    """20 flat bars then a bar that closes above the prior high."""
    bars = []
    for i in range(20):
        p = Decimal("5000")
        bars.append(Bar(instrument="ES", timeframe="5m", ts=now + timedelta(minutes=5 * i),
                        open=p, high=Decimal("5001"), low=Decimal("4999"), close=p,
                        volume=1000, source="test"))
    bars.append(Bar(instrument="ES", timeframe="5m", ts=now + timedelta(minutes=105),
                    open=Decimal("5001"), high=Decimal("5006"), low=Decimal("5000"),
                    close=Decimal("5005"), volume=2000, source="test"))
    return bars


def _ctx(now, trend=Trend.BULL, structure=Structure.BREAKOUT, vol=VolatilityRegime.NORMAL):
    return MarketContext(instrument="ES", timeframe="5m", ts=now, trend=trend,
                         structure=structure, volatility_regime=vol, session=Session.NY_AM,
                         atr=Decimal("2"))


def test_breakout_strategy_emits_long_setup(now):
    strat = BreakoutStrategy(lookback=20, rr=2.0)
    setups = strat.find_setups(_ctx(now), _breakout_bars(now))
    assert len(setups) == 1
    s = setups[0]
    assert s.direction is Direction.LONG and s.reward_risk == 2.0
    assert s.proposed_target > s.proposed_entry > s.proposed_stop


def test_breakout_strategy_stands_down_in_high_vol(now):
    strat = BreakoutStrategy()
    assert strat.find_setups(_ctx(now, vol=VolatilityRegime.HIGH), _breakout_bars(now)) == []


def _setup(now, rr=3.0):
    return Setup(strategy_key="breakout", instrument="ES", direction=Direction.LONG,
                 proposed_entry=Decimal("5000"), proposed_stop=Decimal("4996"),
                 proposed_target=Decimal("5012"), rationale="breakout long",
                 detected_at=now, reward_risk=rr, market_context=_ctx(now))


def _framework(instruments, trades, risk_repo, news_events, *, min_sample):
    risk = RiskEngine(instruments, risk_repo)
    learning = LearningEngine(trades, account_id=1)
    news = NewsEngine(InMemoryNewsRepository())
    if news_events:
        news.load(news_events)
    return DecisionFramework(risk, learning, news, min_score=0.5, min_confidence_sample=min_sample)


def test_decision_enters_on_strong_setup(instruments, trades, risk_repo, flat_account, now):
    fw = _framework(instruments, trades, risk_repo, [], min_sample=0)
    rec = fw.decide(_setup(now), flat_account, now)
    assert rec.action is RecommendationAction.ENTER
    assert rec.suggested_size == 1
    assert "factors" in rec.explanation


def test_decision_waits_on_thin_evidence(instruments, trades, risk_repo, flat_account, now):
    # require 20 own-data trades; we have 0 -> WAIT, not a trade.
    fw = _framework(instruments, trades, risk_repo, [], min_sample=20)
    rec = fw.decide(_setup(now), flat_account, now)
    assert rec.action is RecommendationAction.WAIT
    assert rec.explanation.get("wait_reason") == "insufficient own-data sample"


def test_decision_avoids_in_news_blackout(instruments, trades, risk_repo, flat_account, now):
    events = [NewsEvent(event_time=now + timedelta(minutes=5), name="CPI",
                        severity=NewsSeverity.HIGH, source="test")]
    fw = _framework(instruments, trades, risk_repo, events, min_sample=0)
    rec = fw.decide(_setup(now), flat_account, now)
    assert rec.action is RecommendationAction.AVOID
    assert rec.explanation.get("avoid_reason") == "high-impact news blackout"


def test_decision_avoids_when_risk_vetoes(instruments, trades, risk_repo, flat_account, now):
    from dataclasses import replace
    blown = replace(flat_account, daily_pnl=Decimal("-1000"))
    fw = _framework(instruments, trades, risk_repo, [], min_sample=0)
    rec = fw.decide(_setup(now), blown, now)
    assert rec.action is RecommendationAction.AVOID
    assert rec.explanation.get("avoid_reason") == "risk veto"
