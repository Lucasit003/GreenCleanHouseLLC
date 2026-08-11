#!/usr/bin/env python3
"""Run the test suite with no third-party test runner.

    python tests/run.py            # everything
    python tests/run.py pipeline   # only modules matching "pipeline"

pytest also works if you have it (`pytest tests/`), but is not required.
"""

from __future__ import annotations

import importlib
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MODULES = ["tests.test_pipeline", "tests.test_integrations", "tests.test_render"]


def main(argv: list[str]) -> int:
    selected = [m for m in MODULES if not argv or any(a in m for a in argv)]
    passed, failed = 0, []

    for module_name in selected:
        module = importlib.import_module(module_name)
        print(f"\n{module_name}")
        tests = sorted(n for n in dir(module) if n.startswith("test_"))
        for name in tests:
            started = time.monotonic()
            try:
                getattr(module, name)()
            except Exception:  # noqa: BLE001 - a failing test must not stop the run
                failed.append((module_name, name))
                print(f"  FAIL  {name}")
                print("        " + traceback.format_exc().replace("\n", "\n        ").rstrip())
            else:
                passed += 1
                elapsed = time.monotonic() - started
                suffix = f"  ({elapsed:.1f}s)" if elapsed > 0.5 else ""
                print(f"  ok    {name}{suffix}")

    print(f"\n{passed} passed, {len(failed)} failed")
    for module_name, name in failed:
        print(f"  {module_name}.{name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
