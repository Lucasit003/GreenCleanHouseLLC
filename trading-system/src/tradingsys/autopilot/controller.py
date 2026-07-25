"""Autopilot controller — autonomous execution without a per-trade human click.

This is the component that lets the system "trade without you clicking a
button." It does not weaken any safety property. It replaces the human click
with a human-armed ``AutonomousPolicy`` and keeps the Risk Engine veto in front
of every order. Every decision — execute, skip, or veto — returns an auditable
``AutopilotOutcome``.

Kill switch: ``disarm()`` sets the policy inactive; the very next ``handle`` call
refuses to trade.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..domain.types import (
    Authorization,
    AutonomousPolicy,
    AutopilotDisposition,
    AutopilotOutcome,
    Recommendation,
    RecommendationAction,
)
from ..engines.journal.engine import JournalEngine
from ..engines.risk.engine import RiskEngine
from ..interfaces.execution import ExecutionEngine
from ..interfaces.repository import RecommendationRepository


class AutopilotController:
    def __init__(
        self,
        *,
        risk: RiskEngine,
        execution: ExecutionEngine,
        journal: JournalEngine,
        recommendations: RecommendationRepository,
        policy: AutonomousPolicy,
    ) -> None:
        self._risk = risk
        self._execution = execution
        self._journal = journal
        self._recs = recommendations
        self._policy = policy

    # --- policy lifecycle -------------------------------------------------
    def current_policy(self) -> AutonomousPolicy:
        return self._policy

    def arm(self, policy: AutonomousPolicy, armed_by: str) -> AutonomousPolicy:
        if not armed_by:
            raise ValueError("arming autonomous trading requires a human 'armed_by'")
        self._policy = AutonomousPolicy(
            **{**policy.__dict__, "enabled": True, "armed_by": armed_by, "armed_at": datetime.utcnow()}
        )
        return self._policy

    def disarm(self, by: str, reason: str) -> None:
        # Kill switch. Also flatten open positions for safety.
        self._policy = AutonomousPolicy(**{**self._policy.__dict__, "enabled": False})
        self._execution.flatten(0, reason=f"autopilot disarmed by {by}: {reason}")

    # --- policy gate ------------------------------------------------------
    def _policy_reasons(self, rec: Recommendation) -> list[str]:
        p = self._policy
        reasons: list[str] = []
        if rec.score is not None and rec.score < p.min_score:
            reasons.append(f"score {rec.score} < policy min_score {p.min_score}")
        if rec.confidence is not None and rec.confidence < p.min_confidence:
            reasons.append(f"confidence {rec.confidence} < policy min_confidence {p.min_confidence}")
        if p.allowed_strategies and rec.setup and rec.setup.strategy_key not in p.allowed_strategies:
            reasons.append(f"strategy {rec.setup.strategy_key} not in policy allow-list")
        if p.allowed_sessions and rec.setup and rec.setup.market_context:
            if rec.setup.market_context.session not in p.allowed_sessions:
                reasons.append("session not in policy allow-list")
        if p.block_high_impact_news and rec.news_risk.get("in_blackout"):
            reasons.append("high-impact news blackout in effect")
        return reasons

    # --- the core loop step ----------------------------------------------
    def handle(self, recommendation: Recommendation) -> AutopilotOutcome:
        rec_id = recommendation.id

        if not self._policy.is_active:
            return AutopilotOutcome(AutopilotDisposition.SKIPPED_DISARMED, rec_id,
                                    reasons=("autonomous policy is not armed",))

        if recommendation.action is not RecommendationAction.ENTER:
            return AutopilotOutcome(AutopilotDisposition.SKIPPED_NOT_ENTER, rec_id,
                                    reasons=(f"action is {recommendation.action.value}",))

        policy_reasons = self._policy_reasons(recommendation)
        if policy_reasons:
            return AutopilotOutcome(AutopilotDisposition.SKIPPED_POLICY, rec_id,
                                    reasons=tuple(policy_reasons))

        assert recommendation.setup is not None
        account = self._execution.account_state(recommendation.account_id)
        risk_decision = self._risk.evaluate(recommendation.setup, account)
        if not risk_decision.approved:
            return AutopilotOutcome(AutopilotDisposition.VETOED_BY_RISK, rec_id,
                                    reasons=risk_decision.veto_reasons,
                                    risk_decision=risk_decision)

        # All gates passed — authorize autonomously (honest, audited) and execute.
        auth = Authorization.autonomous(
            policy_version=self._policy.version,
            armed_by=self._policy.armed_by or "unknown",
        )
        trade = self._execution.submit(recommendation, risk_decision, auth)
        trade = self._journal.open_trade(trade)
        return AutopilotOutcome(AutopilotDisposition.EXECUTED, rec_id,
                                risk_decision=risk_decision, trade=trade)

    def run_once(self, account_id: int) -> Optional[AutopilotOutcome]:
        feed = self._recs.feed(account_id, limit=1)
        if not feed:
            return None
        return self.handle(feed[0])
