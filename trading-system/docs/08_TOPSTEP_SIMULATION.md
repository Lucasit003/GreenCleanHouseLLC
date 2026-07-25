# Deliverable 8 — Topstep Combine Simulation

> **Goal:** make fake trades *as if you were in a funded-account evaluation*,
> under the site's real rules, so you can practice passing the Combine before you
> ever pay for one.

## ⚠️ Verify the rules first

Prop-firm rules change and vary by program and account size. The numbers live in
[`config/topstep.json`](../config/topstep.json) and are the **widely-known
Trading Combine values, not authoritative current terms**. Open Topstep's site,
confirm the numbers for the account you plan to buy, and edit the JSON. The
simulator reads whatever is in that file.

One deliberate simplification: the real Topstep trailing max-loss trails your
**intraday** equity *including open profit*. This simulator trails on
**realized** (closed-trade) equity, which is slightly **more lenient**. So treat
a pass here as *necessary but not sufficient* — if you can't pass the simulation,
you definitely can't pass the real thing.

## What it models

| Rule | Modeled as |
|------|-----------|
| **Trailing maximum loss** | `peak_equity − max_loss_limit`, **locked at the starting balance** once you're up by the buffer (the distinctive Topstep mechanic) |
| **Daily loss limit** | per-day realized P&L; `lockout` (stop for the day) or `fail`, per config |
| **Profit target** | realized P&L must reach it to pass |
| **Minimum trading days** | distinct days with ≥1 trade |
| **Contract cap** | max contracts per order for the account size |
| **Consistency rule** | optional: no single day exceeds `consistency_pct` of total profit |

State is one of `active`, `passed`, `failed` (with a reason). The simulation
**halts the instant** the Combine passes or fails — just like the real evaluation.

## How it stays honest to the live system

The generic **Risk Engine is configured from the prop-firm profile** (daily loss
→ `max_daily_loss`, trailing max loss → `max_drawdown`, contract cap →
`max_contracts`), and `TopstepAccount.to_account_state()` maps the trailing
drawdown so that `current_drawdown ≥ max_loss_limit` is *exactly*
`equity ≤ trailing_threshold`. So the **same veto that will guard live trading**
enforces the Combine here — the sim isn't a separate code path that could drift
from reality. On top of that, `TopstepAccount.can_trade()` adds the projected
checks the generic engine can't know about: trailing lock, daily lockout, and
"would this order breach a limit *if stopped out*".

## Run it

```
python scripts/topstep_sim.py                 # 50K profile, default seed
python scripts/topstep_sim.py topstep_100k 42 # profile + seed
```

Example output:

```
=== Topstep Trading Combine 50K — Combine simulation (seed=7) ===

Result: ✅ PASSED
Equity:              $58284.97
Realized P&L:        $8284.97  (target $3000, 276.2%)
Trailing max-loss @:  $50000   (room left: $8284.97)   <- locked at starting balance
Daily-loss room:      $1771.82
Trading days:         3 / 2 required
Trades — opened: 51, closed: 51, blocked by rules: 0
```

Change the `seed` to replay different market luck; change `drift`/`volatility` in
the script to practice trending vs. choppy conditions. In a choppy tape you'll
see `blocked by rules` climb as the account refuses trades that would breach the
daily or trailing limits — which is the whole point.

## Important caveats for practice

- The synthetic data and the two demo strategies are **scaffolding to exercise
  the rules**, not a proven edge. A pass here means the *rule machinery* works and
  the *risk controls* hold — it does **not** predict real-account results.
- For realistic practice, drop **real historical ES/NQ bars** in behind the same
  `MarketDataProvider` (a CSV adapter is the natural next addition).
- Passing a simulation is not a trading strategy. The system's real value is the
  discipline it enforces: risk-sized entries, hard limits, honest journaling, and
  the psychology flags.
