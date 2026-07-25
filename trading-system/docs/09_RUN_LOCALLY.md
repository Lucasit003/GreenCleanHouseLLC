# Deliverable 9 — Run It On Your Own Computer

This is the setup for when you're home with your computer. Running it **locally**
is also what keeps you compliant with Topstep's "local execution" rule — the
program runs on *your* machine, not a cloud server.

## One-time setup

1. **Install Python 3.11 or newer** — https://www.python.org/downloads/
   (On the installer, tick "Add Python to PATH".)
2. **Get the code** — download this repo as a ZIP (green "Code" button on
   GitHub → Download ZIP) and unzip it, or if you know git:
   `git clone <repo-url>`
3. Open a terminal in the `trading-system` folder.

That's it — the system needs **no other installs** (pure standard library).

## Run it

```bash
python run.py advise      # tells you the trade right now — places nothing
python run.py auto        # makes the trades autonomously (PAPER) + result
python run.py report      # paper session + full practice report
```

Options: `--profile topstep_50k` (default) and `--seed 7` (change to replay
different market luck).

- **advise** = "tell me what to trade." It reads the market and prints ENTER /
  WAIT / AVOID with entry, stop, target, size, and the reasoning.
- **auto** = "make the trades for me." It runs autonomously under your Topstep
  account rules and reports whether it would have passed the Combine.

Everything is **paper/simulated** on synthetic data until you do the two steps
below. **No real order is placed by any command yet.**

## Going live later (two local steps, in order)

### Step A — real market data (read-only, safe)
Connect a data feed so it reads real prices instead of synthetic ones. I build a
`MarketDataProvider` adapter for your source (TopstepX API, Tradovate, or a data
vendor). Your API key goes in a local `.env` file (copy `.env.example`) that the
repo **never** commits.

### Step B — live execution (the gated step)
I build a broker adapter behind the existing `ExecutionEngine` for your platform
(TopstepX / Tradovate) and wire `run.py auto` to route through it. Before this is
switched on:
- confirm your prop firm allows automated + local execution (Topstep: yes,
  local-only);
- credentials live in `.env` / a secrets manager, never in the repo;
- it starts in the platform's **demo/sim** account, and only you flip it to live.

## What to tell me when you're back

1. Which firm/account you bought (Topstep 50K, or Lucid/Tradeify/TPT).
2. Which platform API it uses (TopstepX / Tradovate).
3. That you're ready — I'll build the data adapter first, we verify it reads real
   prices, then wire execution in demo mode before anything live.

Until then, run `advise` / `auto` to get familiar with how it thinks.
