#!/usr/bin/env python3
"""Cron entrypoint. Render runs this on a schedule (e.g. every 10 minutes).

It performs exactly one trading cycle and exits, so it costs only the few
seconds of compute per run.
"""
import logging
import sys

from app.engine import run_once

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def main() -> int:
    result = run_once()
    if result.ok:
        rec = result.recommendation
        action = rec.action if rec else "?"
        print(f"[cycle ok] candidates={result.candidates} rec={action} | {result.note}")
        if rec:
            print(f"  rationale: {rec.rationale}")
        for t in result.executed:
            print(f"  executed {t.mode} {t.action} {t.base} qty={t.quantity:.6f} @ {t.price:.6f}")
        return 0
    print(f"[cycle error] {result.error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
