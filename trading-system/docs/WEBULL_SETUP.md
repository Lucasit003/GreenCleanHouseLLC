# Webull Setup Checklist — do this when you're at your computer

The goal: connect the trading system to your **Webull futures paper account** so
`python run.py auto` places simulated trades on real market data — for free, no
prop-firm subscription. Everything below is a **desktop/browser** task; it can't
be finished on a phone, and the system itself only runs on a computer.

Already done (from your phone) ✅
- Webull account created
- Futures **paper** account exists (yours: `DEN38CJ3`)
- Paper trading mode is ON

---

## Part 1 — Get API access (browser, ~10 min + 1–3 day review)

- [ ] On a computer, go to **https://www.webull.com/open-api** and sign in.
- [ ] Click **Apply / Get Started** for OpenAPI access.
- [ ] Complete the application. Approval takes **1–3 days** — you'll get an email.
- [ ] After approval, go to **https://developer.webull.com** → **API Management**.
- [ ] **Create an app / generate API keys.** You'll get:
      - an **App Key / App ID**
      - an **App Secret**
      - (note which **region/endpoint** it's for — US)
- [ ] Make sure the keys are set to **PAPER / simulation**, not live.

> ⚠️ Do NOT paste these keys into the chat. They go in a local file (Part 2)
> that the repo is configured to never upload.

---

## Part 2 — Get the system on your computer

- [ ] Install **Python 3.11+** — https://www.python.org/downloads/
      (tick "Add Python to PATH" during install).
- [ ] Download this repo: GitHub → green **Code** button → **Download ZIP** →
      unzip. (Or `git clone` if you use git.)
- [ ] Open a terminal in the `trading-system` folder.
- [ ] Confirm it runs (paper/synthetic, no keys needed yet):
      ```
      python run.py advise
      python run.py auto
      ```
      If you see output, you're ready.

- [ ] Copy `.env.example` to a new file named `.env` in `trading-system/`.
- [ ] Put your Webull keys in `.env` (I'll tell you the exact variable names when
      we wire it). The repo's `.gitignore` already blocks `.env` from uploading.

---

## Part 3 — Tell me "ready"

When Parts 1 and 2 are done, message me: **"Webull ready"** plus
- confirmation the keys are **paper**, and
- your futures paper account id (`DEN38CJ3`).

Then I will:
1. Build a **`WebullMarketDataProvider`** (read real prices) and verify it first.
2. Build a **Webull paper `ExecutionEngine`** adapter.
3. Wire `run.py auto` to route through it — so trades land in your Webull paper
   account, under the Topstep 50K rule limits the system already enforces.
4. We watch it run in paper before anything else.

---

### Reminders
- This is **practice**, free, and risk-free — no real money, ever, in paper mode.
- Webull paper ≠ the Topstep evaluation. It's the free proving ground first.
- The live/real step (a prop firm) comes later, only after this works and only
  with you running it locally.
