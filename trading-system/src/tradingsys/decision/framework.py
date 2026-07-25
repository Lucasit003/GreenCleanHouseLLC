"""Decision Framework (Step 10).

The composition point. It takes a candidate ``Setup`` plus the live account and
produces a single scored, fully explainable ``Recommendation`` — ENTER, WAIT, or
AVOID — by combining:

  * reward:risk of the setup,
  * strategy confidence (own-data, overfitting-guarded),
  * trend alignment and volatility regime from the MarketContext,
  * news risk (hard blackout),
  * and the Risk Engine's authoritative veto.

Two guarantees the brief demands:
  * a risk-vetoed setup ALWAYS becomes AVOID;
  * weak evidence ALWAYS becomes WAIT (patience, not a trade).
Every recommendation carries the full factor breakdown in ``explanation``.
"""
from __future__ import annotations

from datetime import datetime

from ..domain.types import (
    AccountState,
    Recommendation,
    RecommendationAction,
    Setup,
    Trend,
    VolatilityRegime,
)
from ..engines.learning.engine import LearningEngine
from ..engines.news.engine import NewsEngine
from ..engines.risk.engine import RiskEngine

# Scoring weights (documented, tunable — measured, not sacred).
_W_RR, _W_CONF, _W_TREND, _W_VOL = 0.35, 0.30, 0.20, 0.15


class DecisionFramework:
    def __init__(
        self,
        risk: RiskEngine,
        learning: LearningEngine,
        news: NewsEngine,
        *,
        min_score: float = 0.55,
        min_confidence_sample: int = 20,
    ) -> None:
        self._risk = risk
        self._learning = learning
        self._news = news
        self._min_score = min_score
        self._min_conf_sample = min_confidence_sample

    def decide(self, setup: Setup, account: AccountState, at: datetime) -> Recommendation:
        ctx = setup.market_context
        explanation: dict[str, object] = {"setup_rationale": setup.rationale}

        # 1) News blackout is a hard stop.
        news_risk = self._news.news_risk(setup.instrument, at)
        explanation["news_risk"] = news_risk
        if news_risk.get("in_blackout"):
            return self._avoid(setup, account, at, "high-impact news blackout", explanation, news_risk)

        # 2) Risk veto is authoritative.
        risk_decision = self._risk.evaluate(setup, account)
        explanation["risk_checks"] = risk_decision.checks
        if not risk_decision.approved:
            explanation["risk_veto"] = list(risk_decision.veto_reasons)
            return self._avoid(setup, account, at, "risk veto", explanation, news_risk)

        # 3) Confidence (own-data, shrunk toward prior when evidence is thin).
        conf = self._learning.update_confidence(setup.strategy_key)

        # 4) Component factors in [0,1].
        rr = setup.reward_risk or 0.0
        rr_factor = max(0.0, min(rr / 3.0, 1.0))
        conf_factor = conf.value
        if ctx is None:
            trend_factor, vol_factor = 0.7, 1.0
        else:
            if (setup.direction.value == "long" and ctx.trend is Trend.BULL) or (
                setup.direction.value == "short" and ctx.trend is Trend.BEAR
            ):
                trend_factor = 1.0
            elif ctx.trend is Trend.RANGE:
                trend_factor = 0.7
            else:
                trend_factor = 0.4  # counter-trend
            vol_factor = {
                VolatilityRegime.NORMAL: 1.0,
                VolatilityRegime.LOW: 0.9,
                VolatilityRegime.HIGH: 0.7,
            }[ctx.volatility_regime]

        score = (
            _W_RR * rr_factor + _W_CONF * conf_factor
            + _W_TREND * trend_factor + _W_VOL * vol_factor
        )
        explanation["factors"] = {
            "reward_risk": rr, "rr_factor": round(rr_factor, 3),
            "confidence": conf_factor, "confidence_sample": conf.sample_size,
            "trend_factor": trend_factor, "volatility_factor": vol_factor,
            "weights": {"rr": _W_RR, "conf": _W_CONF, "trend": _W_TREND, "vol": _W_VOL},
        }
        explanation["score"] = round(score, 4)

        # 5) Weak evidence -> WAIT. Two ways to be "weak": low score, or too
        #    little own-data behind the confidence to trust it.
        thin_evidence = conf.sample_size < self._min_conf_sample
        if score < self._min_score or thin_evidence:
            reason = "score below threshold" if score < self._min_score else "insufficient own-data sample"
            explanation["wait_reason"] = reason
            return Recommendation(
                action=RecommendationAction.WAIT, account_id=account.account_id, created_at=at,
                setup=setup, direction=setup.direction, score=round(score, 4),
                confidence=conf_factor, explanation=explanation, news_risk=news_risk,
            )

        # 6) ENTER — sized by the Risk Engine.
        return Recommendation(
            action=RecommendationAction.ENTER, account_id=account.account_id, created_at=at,
            setup=setup, direction=setup.direction, score=round(score, 4),
            confidence=conf_factor, suggested_size=risk_decision.computed_size,
            entry=setup.proposed_entry, stop=setup.proposed_stop, target=setup.proposed_target,
            explanation=explanation, news_risk=news_risk,
        )

    def _avoid(self, setup, account, at, reason, explanation, news_risk) -> Recommendation:
        explanation["avoid_reason"] = reason
        return Recommendation(
            action=RecommendationAction.AVOID, account_id=account.account_id, created_at=at,
            setup=setup, direction=setup.direction, explanation=explanation, news_risk=news_risk,
        )
