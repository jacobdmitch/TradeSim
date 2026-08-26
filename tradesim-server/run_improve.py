#!/usr/bin/env python3
"""Cron entrypoint for the self-improvement loop. Render runs this on its own,
much less frequent schedule than the trading cycle (see render.yaml) — it
backtests the live rotation thresholds against recent market history and, if
warranted, nudges them. See app/improve.py for the guardrails.
"""
import logging
import sys

from app.improve import run_improvement_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def main() -> int:
    try:
        result = run_improvement_cycle()
    except Exception as e:  # noqa: BLE001 - this cron must exit cleanly either way
        print(f"[improve error] {e}", file=sys.stderr)
        return 1
    if result is None:
        print("[improve] no change this run")
    else:
        print(f"[improve] applied: {result['changes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
