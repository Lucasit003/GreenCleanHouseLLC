"""Webull auth + API discovery.

Loads your keys from .env, creates the SDK clients against the PAPER (sandbox)
endpoint, and prints the available methods so we can build the adapter. Prints
NO secrets. Run from the trading-system folder:

    py scripts/webull_test.py
"""
from __future__ import annotations

import importlib
import pkgutil
import traceback
from pathlib import Path


def load_env() -> dict:
    for cand in (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if cand.exists():
            env = {}
            for line in cand.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.split("#", 1)[0].strip()
            return env
    return {}


def main() -> None:
    env = load_env()
    key = env.get("WEBULL_APP_KEY", "")
    sec = env.get("WEBULL_APP_SECRET", "")
    region = env.get("WEBULL_REGION", "us")
    print("keys present:",
          bool(key) and not key.startswith("__"), "/",
          bool(sec) and not sec.startswith("__"), " region:", region)

    print("\n-- SDK layout --")
    for sub in ("core", "data", "trade"):
        try:
            m = importlib.import_module("webull." + sub)
            print(f"webull.{sub}:", [x.name for x in pkgutil.iter_modules(m.__path__)])
        except Exception as e:  # noqa: BLE001
            print(f"webull.{sub}: ERROR {type(e).__name__}: {e}")

    print("\n-- Clients (PAPER/sandbox) --")
    try:
        from webull.core.client import ApiClient
        api = ApiClient(key, sec, region)
        api.add_endpoint(region, "api.sandbox.webull.com")
        print("ApiClient OK. methods:", [a for a in dir(api) if not a.startswith("_")])

        from webull.trade.trade_client import TradeClient
        tc = TradeClient(api)
        print("TradeClient methods:", [a for a in dir(tc) if not a.startswith("_")])
    except Exception as e:  # noqa: BLE001
        print("CLIENT ERROR:", type(e).__name__, e)
        traceback.print_exc()


if __name__ == "__main__":
    main()
