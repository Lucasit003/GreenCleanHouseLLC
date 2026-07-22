# Deliverable 7 — Autonomous Trading (no per-trade click)

> **Can the system trade without a human clicking a button?** Yes. This document
> explains how it does so *safely*, what changed in the architecture to support
> it, and the hard rules that autonomy does **not** get to bend.

## ⚠️ Read this before enabling live autonomy

1. **Verify Topstep's automation rules first.** Many prop firms restrict or
   prohibit fully-unattended algorithmic trading, and a violation can void a
   funded account. Confirm the current Topstep policy for *your* account before
   ever setting `live=True`. The software cannot check this for you.
2. **Paper is the default.** `AutonomousPolicy.live` defaults to `False`.
   Autonomy runs against the `PaperExecutionEngine` (simulated fills) until a
   human deliberately promotes it.
3. **The Risk Engine veto is now the last line of defense.** With no human
   click, a bug or bad tick has one thing between it and your account: the Risk
   Engine. That is why it was built *before* autonomy was wired.
4. **This is not financial advice and guarantees nothing.** Autonomy does not
   improve edge; it removes the human backstop. Use small size and supervise.

## The model: arm a policy, don't click trades

Instead of a human confirming each trade, a human **arms an `AutonomousPolicy`
once**. The `Autopilot` then auto-executes any recommendation that clears *both*
the policy thresholds *and* the Risk Engine veto. Disarming is the instant kill
switch.

```
recommendation (ENTER)
   ├─ policy.is_active?              no → SKIPPED_DISARMED
   ├─ score/confidence/strategy/     no → SKIPPED_POLICY
   │  session/news gates pass?
   ├─ RiskEngine.evaluate approves?  no → VETOED_BY_RISK
   └─ all yes → ExecutionEngine.submit(Authorization.autonomous(policy, armed_by))
                                     → EXECUTED  (journaled)
```

Every branch returns an auditable `AutopilotOutcome`. Nothing is silent.

## What changed in the architecture

Autonomy did **not** require loosening any safety property — it slotted into the
existing seam:

| Change | File | Why |
|--------|------|-----|
| `Authorization` type (human *or* autonomous) | `domain/types.py` | Records *how* an order was authorized — autonomy never fakes a human click |
| `AutonomousPolicy` (armed by a human, paper by default, kill switch) | `domain/types.py` | The one-time human sign-off that replaces per-trade clicks |
| `ExecutionEngine.submit(..., authorization)` | `interfaces/execution.py` | Accepts an explicit authorization instead of a bare `human_confirmed` bool |
| `AutopilotController` | `interfaces/autopilot.py`, `autopilot/controller.py` | Orchestrates policy-gate → risk-veto → execute |
| Risk Engine pulled forward (was Step 9) | `engines/risk/engine.py` | Mandatory backstop once the human click is gone |

## Safety properties (each has a passing test)

- **Disarmed → never trades.** `test_disarmed_policy_never_trades`
- **Kill switch stops trading (and flattens).** `test_kill_switch_stops_trading`
- **Weak evidence → skipped, not traded.** `test_weak_evidence_skipped_by_policy`
- **Risk veto blocks autonomous entry.** `test_risk_veto_blocks_autonomous_trade`
- **Execution refuses a malformed autonomous authorization.**
  `test_paper_execution_refuses_autonomous_without_armed_policy`
- **Autonomy still cannot change risk rules.**
  `test_learning_cannot_change_rules_without_human`
- **Happy path executes with no human click, correctly sized + journaled.**
  `test_autonomous_trade_executes_without_human_click`

## How to arm it (paper)

```python
from tradingsys.domain.types import AutonomousPolicy
policy = AutonomousPolicy(version=1, min_score=0.65, min_confidence=0.6,
                          allowed_strategies=("orb", "trend_pullback"),
                          max_contracts=2)          # live defaults to False
autopilot.arm(policy, armed_by="lucas")             # requires a human
# ... the loop:
autopilot.run_once(account_id=1)                    # executes iff policy + risk allow
# kill switch:
autopilot.disarm(by="lucas", reason="stepping away")
```

## What is still required before this is "done" for live

Autonomy is proven end-to-end **in paper**. Before live it needs (see
`06_IMPLEMENTATION_ORDER.md`): the Decision Framework (Step 10) producing real
recommendations, the News Engine blackout wiring (Step 11), a live
`TopstepExecutionEngine` behind the same interface (Step 15), plus a supervised
trading loop with heartbeat/alerting and a reconciliation + hard kill-switch
runbook. Live autonomy is the *last* thing that gets switched on, not the first.
