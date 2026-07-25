"""Autopilot contract — autonomous execution without a per-trade human click.

The Autopilot is what lets the system trade on its own. It does NOT relax any
safety property; it *replaces the human click* with an armed, human-authorized
``AutonomousPolicy`` and keeps the Risk Engine's hard veto in front of every
order. Disarming the policy is the instant kill switch.

Authorization flow for an autonomous trade:

    recommendation (ENTER)
        └─ policy.is_active?            no  → SKIPPED_DISARMED
        └─ passes policy thresholds?    no  → SKIPPED_POLICY
        └─ RiskEngine.evaluate approves? no → VETOED_BY_RISK
        └─ yes to all → ExecutionEngine.submit(Authorization.autonomous(...))
                                        → EXECUTED (journaled)
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..domain.types import AutonomousPolicy, AutopilotOutcome, Recommendation


@runtime_checkable
class AutopilotController(Protocol):
    def current_policy(self) -> AutonomousPolicy:
        """Return the active autonomous policy (may be disarmed)."""
        ...

    def arm(self, policy: AutonomousPolicy, armed_by: str) -> AutonomousPolicy:
        """Arm autonomous trading. Requires a human ``armed_by``. Audited."""
        ...

    def disarm(self, by: str, reason: str) -> None:
        """Kill switch: stop all autonomous execution immediately."""
        ...

    def handle(self, recommendation: Recommendation) -> AutopilotOutcome:
        """Evaluate one recommendation and execute it iff policy + risk allow.

        Pure with respect to safety: never executes when disarmed, when the
        recommendation is not ENTER, when policy thresholds fail, or when the
        Risk Engine vetoes. Every path returns an auditable ``AutopilotOutcome``.
        """
        ...

    def run_once(self, account_id: int) -> Optional[AutopilotOutcome]:
        """Pull the latest recommendation for an account and handle it (one tick
        of the trading loop). Returns None if there is nothing to act on.
        """
        ...
