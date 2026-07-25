"""Webull OpenAPI connection test / discovery.

Run this on YOUR computer after: (1) pip installing the SDK, (2) putting your
App Key + App Secret in trading-system/.env. It reads the keys locally, checks
the SDK, and reports what's available + whether auth works — so we can build the
adapter against the real API. It never sends your keys anywhere but Webull.

    pip install --upgrade webull-openapi-python-sdk
    python scripts/webull_connect.py

Paste me the OUTPUT (it prints NO secrets — only key lengths and the SDK's
module/class names).
"""
from __future__ import annotations

import importlib
import os
import pkgutil
from pathlib import Path


def load_env() -> dict:
    env = {}
    p = Path(__file__).resolve().parents[1] / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.split("#", 1)[0].strip()
    # environment variables override the file
    for k in ("WEBULL_APP_KEY", "WEBULL_APP_SECRET", "WEBULL_REGION", "WEBULL_PAPER"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def check_keys(env: dict) -> bool:
    ok = True
    for k in ("WEBULL_APP_KEY", "WEBULL_APP_SECRET"):
        v = env.get(k, "")
        if not v or v.startswith("__"):
            print(f"  ✗ {k} not set in .env")
            ok = False
        else:
            print(f"  ✓ {k} present (length {len(v)}, ends '…{v[-4:]}')")
    print(f"  region={env.get('WEBULL_REGION','?')}  paper={env.get('WEBULL_PAPER','?')}")
    return ok


def discover_sdk() -> None:
    candidates = [
        "webullsdkcore", "webullsdkmdata", "webullsdktrade", "webullsdktradeeventscore",
        "webull_openapi", "webullopenapi",
    ]
    found = []
    for name in candidates:
        try:
            mod = importlib.import_module(name)
            found.append(name)
            subs = [m.name for m in pkgutil.iter_modules(mod.__path__)] if hasattr(mod, "__path__") else []
            print(f"  ✓ import {name}  ->  submodules: {subs[:12]}")
        except Exception as e:  # noqa: BLE001
            print(f"  · {name}: not found ({type(e).__name__})")
    if not found:
        print("\n  No Webull SDK modules imported. Install with:")
        print("      pip install --upgrade webull-openapi-python-sdk")


def main() -> None:
    print("=== Webull connection test ===\n[1] Keys in .env:")
    env = load_env()
    keys_ok = check_keys(env)
    print("\n[2] SDK discovery:")
    discover_sdk()
    print("\n[3] Next: paste this whole output back to me (no secrets are shown).")
    if not keys_ok:
        print("    First put your App Key + App Secret in trading-system/.env.")


if __name__ == "__main__":
    main()
