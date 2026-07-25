# Start Here — Tonight

Follow these in order. Total hands-on time ≈ 15 minutes. Two tracks run in
parallel: **real-data backtests (we do this tonight)** and **Webull live paper
(starts in a few days once the API is approved).**

---

## Track A — Get the code running (≈5 min)

1. **Install Python 3.11+** — https://www.python.org/downloads/
   (On the installer, check **"Add Python to PATH".**)
2. **Download the repo:** GitHub → green **Code** button → **Download ZIP** → unzip.
3. Open a terminal **in the `trading-system` folder** and run:
   ```
   python run.py advise
   python run.py auto
   ```
   If you see output, the whole system works on your machine. ✅

---

## Track B — Real historical data TONIGHT (no waiting) ⭐

This is the big one — it needs no API approval, just a browser download.

1. In your browser, download a CSV of real bars. Easiest options:
   - **stooq.com** → search a symbol (try `SPY` or `ES.F`) → **"Download data in csv"**
   - or **nasdaq.com** → search `SPY` → **Historical** → **Download**
   - Best: an **intraday (5-min)** export if the source offers it; daily works too.
2. Put the file in `trading-system/data/` (create the folder). Name it e.g. `es.csv`.
3. Tell me the filename and I'll run the **full gauntlet on real prices**:
   `python run.py backtest --csv data/es.csv`, the tournament, and the Monte-Carlo.
   That's when the pass-rate numbers finally mean something.

---

## Track C — Apply for Webull API (start tonight, approves in 1–3 days)

1. On the computer, go to **https://www.webull.com/open-api** → sign in → **Apply**.
2. After approval (email, 1–3 days), go to **https://developer.webull.com** →
   **API Management** → **create app / generate keys**. Set it to **PAPER**.
3. Copy `trading-system/.env.example` to `trading-system/.env` and paste your keys
   into the `WEBULL_*` fields. (The repo ignores `.env` — keys stay on your machine.)
4. Message me **"Webull ready."** I'll build the data adapter first (read-only),
   verify it pulls real prices, then wire paper execution — nothing live.

---

## What to send me tonight

Just one of these, whichever you get to:
- **"code runs"** — and/or the **CSV filename** you dropped in `data/` → I run real-data backtests immediately.
- **"applied for Webull"** → I'll have the adapter ready for when your keys land.

## Honest expectation-setting
- **Tonight:** code running + real-data backtests from a CSV. Big step.
- **In a few days:** Webull API approved → live paper forward-testing.
- Reminder: real data will probably show the bots are **weaker** than the synthetic
  runs suggested. That's the point — we want the truth before any funded money.
