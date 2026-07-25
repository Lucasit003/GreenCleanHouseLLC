# Webull Adapter — Handoff Brief (for a local coding agent)

You're finishing the **Webull paper-trading integration** for this modular
futures trading system. Everything is Python 3.11+ (user is on 3.14 — watch for
SDK compat). The SDK is already installed. Below is exactly what's known and
what to build. Keep everything **PAPER** — no live trading.

## Goal
Implement two adapters behind the existing interface contracts, then wire them
into `run.py`, and verify against the user's Webull **paper** account:
1. `WebullMarketDataProvider` → `src/tradingsys/interfaces/market_data.py`
   (`MarketDataProvider`: `get_history`, `stream`, `get_instrument_spec`),
   returning `tradingsys.domain.types.Bar`.
2. `WebullPaperExecutionEngine` → `src/tradingsys/interfaces/execution.py`
   (`ExecutionEngine`: `account_state`, `submit`, `flatten`, `broker_info`,
   `is_paper`). Must honor the existing safety rules (approved RiskDecision +
   valid Authorization required).

## Credentials (already set up)
- `.env` in the `trading-system/` folder holds: `WEBULL_APP_KEY`,
  `WEBULL_APP_SECRET`, `WEBULL_REGION=us`, `WEBULL_PAPER=true`,
  `WEBULL_FUTURES_ACCOUNT_ID`. Read from there; never hardcode or print secrets.
- The app is registered in the **PaperTrade** environment with Quotes/Trading
  permission.

## SDK facts discovered (verified on the user's machine)
- Package: `webull-openapi-python-sdk` (v2.0.15). Top module: `webull` with
  subpackages `core`, `data`, `trade`.
- Auth works (HMAC-SHA256 signing succeeds):
  ```python
  from webull.core.client import ApiClient
  api = ApiClient(app_key, app_secret, "us")
  api.add_endpoint("us", HOST)          # HOST still TBD — see below
  ```
- **HOST is unresolved.** `api.sandbox.webull.com` returns HTTP 404 "Route Not
  Found" (not an auth error). Find the correct US paper host — check the
  `webull.core.endpoint` module constants, the official docs at
  developer.webull.com, or try production `api.webull.com`. This is the first
  thing to fix.
- Account list (no id needed): `TradeClient(api).account_v2.get_account_list()`.
- Account: `tc.account.get_account_balance(account_id)`,
  `get_account_position(account_id)`, `get_account_profile(account_id)`.
- Orders: `tc.order.place_order(...)`, `cancel_order`, `list_open_orders`,
  `list_today_orders`, `query_order_detail`, `replace_order`.
- Market data: `from webull.data.data_client import DataClient; dc = DataClient(api)`
  exposes sub-objects: `market_data` (stocks), **`futures_market_data`** (ES/NQ),
  `instrument`, `option_market_data`, `crypto_market_data`, `screener`,
  `watchlist`. Introspect `dir(dc.futures_market_data)` for the quote/bar methods
  and their arg signatures (likely need a category/market + symbols).
- Tip: `import logging; logging.disable(logging.CRITICAL)` silences noisy SDK
  error logs during development.

## Suggested order of work
1. Resolve HOST → get `account_v2.get_account_list()` returning the real account.
2. Introspect `dc.futures_market_data` methods; pull a live ES snapshot + bars.
3. Build `WebullMarketDataProvider` mapping Webull bars → `domain.types.Bar`.
4. Re-run the existing backtests on real bars via the CSV/live path.
5. Build `WebullPaperExecutionEngine`; place ONE paper order end-to-end.
6. Wire `run.py` (e.g. `--provider webull`) to use them.

## Reuse, don't reinvent
- Domain types: `src/tradingsys/domain/types.py` (Bar, Trade, AccountState, etc.)
- Existing engines/pipeline: `src/tradingsys/engines/…`, `decision/`, `backtest/`.
- Local runner: `run.py` (advise/auto/backtest/compare) — pure stdlib.
- The interface Protocols in `src/tradingsys/interfaces/` define the contracts to
  satisfy; the rest of the system depends only on those.

Keep it paper, read data first, and confirm each step against the real account
before moving on.
