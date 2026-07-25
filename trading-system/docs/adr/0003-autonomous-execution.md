# ADR 0003 — Autonomous execution via an armed policy (not a per-trade click)

## Status
Accepted

## Context
The original design required a human to confirm every order
(`human_confirmed=True`). The trader asked for the system to trade without
clicking a button per trade. Fully-unattended execution is a legitimate,
well-understood pattern, but removing the human click removes the last manual
backstop, so the safety burden shifts entirely onto code.

## Decision
Replace the per-trade human click with a **human-armed `AutonomousPolicy`** and
an `Autopilot` orchestrator, while keeping every existing safety property:

1. **Authorization is explicit and honest.** `ExecutionEngine.submit` takes an
   `Authorization` that is either `HUMAN` or `AUTONOMOUS`. Autonomous orders
   carry the armed policy version and the human who armed it — they never
   masquerade as a human click.
2. **A human must arm autonomy.** `AutonomousPolicy.is_active` is true only when
   `enabled` *and* `armed_by` is set. `arm()` requires a human.
3. **Paper by default.** `AutonomousPolicy.live` defaults to `False`.
4. **Risk Engine keeps its hard veto** in front of every autonomous order, and
   was pulled forward from Step 9 to be built before autonomy is wired.
5. **Kill switch.** `disarm()` deactivates the policy and flattens positions;
   the next loop tick refuses to trade.
6. **Learning still cannot touch risk rules.** Unchanged and re-tested.

## Consequences
- The system can trade with no per-trade interaction, proven end-to-end in
  paper with tests covering the happy path and every refusal.
- Enabling *live* autonomy remains a deliberate, audited, human action gated on
  the Decision Framework, News wiring, a live broker adapter, and a supervised
  loop with alerting — explicitly the last capability switched on.
- **External constraint:** prop-firm (Topstep) rules on automated trading are a
  compliance matter the software cannot verify; the human must confirm them
  before going live. Documented in `docs/07_AUTONOMOUS_TRADING.md`.
