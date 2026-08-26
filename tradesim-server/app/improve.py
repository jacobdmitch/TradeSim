"""Automated self-improvement loop for the rotation strategy.

Runs on its own schedule (see run_improve.py), separate from the trading
cycle in engine.py. Each run:
  1. Reads the live StrategyParams (the thresholds engine.py is trading with
     right now).
  2. Backtests them against recent real market history, then backtests a
     small neighborhood of nearby variants (one parameter perturbed at a
     time, holding the others fixed — a coordinate-wise local search).
  3. If a variant clearly and consistently beats the live config, nudges
     StrategyParams a bounded step toward it — never a jump straight to the
     backtest "winner", since a single backtest window is noisy.
  4. Logs every change to StrategyChangeLog with the metric that justified
     it, so automated tuning stays inspectable and reversible after the fact.

Safety boundaries:
  - Never touches Settings.enabled or Settings.dry_run. This loop can only
    retune existing rotation thresholds; it can never turn trading on, take
    it live, or change how much money is at risk.
  - Every param is clamped to a hard-coded range (BOUNDS) regardless of what
    a backtest suggests.
  - A param won't be changed again within COOLDOWN_HOURS of its last change.
  - Fails safe: any error here is logged and the cycle no-ops. A bug in this
    module must never disturb the live trading cron.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Optional

from .db import SessionLocal, StrategyChangeLog, get_strategy_params, init_db

log = logging.getLogger("tradesim.improve")

# ---- Guardrails ----
BOUNDS = {
    "enter_threshold_pct": (0.5, 6.0),
    "rotation_threshold_pct": (0.5, 8.0),
    "exit_threshold_pct": (-4.0, 0.0),
    "trailing_stop_pct": (2.0, 12.0),
}
# Perturbation tried for each parameter, one at a time (coordinate search).
STEP_SIZES = {
    "enter_threshold_pct": 0.5,
    "rotation_threshold_pct": 0.5,
    "exit_threshold_pct": 0.5,
    "trailing_stop_pct": 1.0,
}
# Fraction of the way from current -> best-backtested value moved per run.
# Limits how much a single noisy backtest window can swing live trading.
STEP_FRACTION = 0.3
# A variant must beat the current config's score by at least this many
# points (worst walk-forward segment return %, drawdown-penalized) to act.
MIN_IMPROVEMENT_MARGIN = 1.0
# Don't change the same parameter again within this many hours.
COOLDOWN_HOURS = 24
# Skip the cycle entirely if there isn't at least this much history to
# backtest against (bars are hourly).
MIN_HISTORY_BARS = 200


@dataclass
class Variant:
    enter_threshold_pct: float
    rotation_threshold_pct: float
    exit_threshold_pct: float
    trailing_stop_pct: float

    def clamped(self) -> "Variant":
        return replace(self, **{
            k: max(BOUNDS[k][0], min(BOUNDS[k][1], getattr(self, k)))
            for k in BOUNDS
        })


def _load_market_data():
    """Recent real market history, via the same fetch path backtest.py uses."""
    import backtest as bt
    univ = bt.load_universe()
    timeline, closes, vols = bt.align(univ)
    return timeline, closes, vols


def _score(result, timeline) -> float:
    """Walk-forward consistency, not raw return: the worst of the walk-forward
    segments, penalized by drawdown. Rewards a variant that holds up across
    time windows over one that got lucky in a single stretch — the same
    reasoning already used by hand in BACKTEST_RESULTS.md."""
    import backtest as bt
    n = len(timeline)
    segments = bt.WALK_SEGMENTS
    seg = max(n // segments, 1)
    bounds = [(k * seg, (n if k == segments - 1 else (k + 1) * seg)) for k in range(segments)]
    eq = result.equity
    seg_returns = []
    for a, b in bounds:
        end = min(b, n) - 1
        if end < a or a >= len(eq) or end >= len(eq):
            continue
        sv, ev = eq[a], eq[end]
        seg_returns.append((ev / sv - 1) * 100 if sv else 0.0)
    worst = min(seg_returns) if seg_returns else -999.0
    return worst - 0.5 * result.max_dd


def _evaluate(variant: Variant, timeline, closes, vols):
    import backtest as bt
    strat = bt.make_live_v2(enter_th=variant.enter_threshold_pct,
                            rotate_th=variant.rotation_threshold_pct)
    result = bt.run_strategy(
        "variant", strat, timeline, closes, vols,
        start_cash=100.0, use_regime=True, brake_all=True,
        trail_pct=variant.trailing_stop_pct,
    )
    return _score(result, timeline)


def _in_cooldown(session, param: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=COOLDOWN_HOURS)
    last = (
        session.query(StrategyChangeLog)
        .filter(StrategyChangeLog.param == param)
        .order_by(StrategyChangeLog.id.desc())
        .first()
    )
    if last is None:
        return False
    ts = last.ts if last.ts.tzinfo else last.ts.replace(tzinfo=timezone.utc)
    return ts >= cutoff


def run_improvement_cycle(session=None) -> Optional[dict]:
    """Entry point (called by run_improve.py). Returns a summary dict if a
    change was applied, else None. Never raises."""
    own_session = session is None
    if own_session:
        init_db()
        session = SessionLocal()
    try:
        sp = get_strategy_params(session)
        if sp is None:
            return None
        current = Variant(sp.enter_threshold_pct, sp.rotation_threshold_pct,
                          sp.exit_threshold_pct, sp.trailing_stop_pct)

        try:
            timeline, closes, vols = _load_market_data()
        except Exception as e:  # noqa: BLE001 - network/data errors just skip this cycle
            log.warning("market data fetch failed, skipping cycle: %s", e)
            return None
        if len(timeline) < MIN_HISTORY_BARS:
            log.info("not enough history (%d bars), skipping", len(timeline))
            return None

        baseline_score = _evaluate(current, timeline, closes, vols)

        best_variant, best_score = current, baseline_score
        for param, step in STEP_SIZES.items():
            for delta in (step, -step):
                candidate = replace(current, **{param: getattr(current, param) + delta}).clamped()
                score = _evaluate(candidate, timeline, closes, vols)
                if score > best_score:
                    best_variant, best_score = candidate, score

        if best_variant is current or best_score < baseline_score + MIN_IMPROVEMENT_MARGIN:
            log.info("no variant beat baseline by the required margin (best=%.2f base=%.2f)",
                     best_score, baseline_score)
            return None

        changes = {}
        for param in STEP_SIZES:
            old = getattr(current, param)
            target = getattr(best_variant, param)
            if abs(target - old) < 1e-9 or _in_cooldown(session, param):
                continue
            lo, hi = BOUNDS[param]
            stepped = max(lo, min(hi, old + (target - old) * STEP_FRACTION))
            if abs(stepped - old) < 1e-6:
                continue
            changes[param] = (old, stepped)

        if not changes:
            return None

        reason = (
            f"local search variant scored {best_score:.2f} vs live {baseline_score:.2f} "
            f"(worst walk-forward segment %, drawdown-penalized) over {len(timeline)} bars "
            f"(~{len(timeline) / 24:.0f}d); stepped {STEP_FRACTION:.0%} of the way there."
        )
        for param, (old, new) in changes.items():
            setattr(sp, param, new)
            session.add(StrategyChangeLog(
                param=param, old_value=old, new_value=new, reason=reason,
                metric_before=baseline_score, metric_after=best_score,
            ))
        session.commit()
        log.info("applied changes: %s", changes)
        return {"changes": changes, "baseline_score": baseline_score, "best_score": best_score}

    except Exception:  # noqa: BLE001 - a tuning bug must never touch live trading
        log.exception("improvement cycle failed")
        try:
            session.rollback()
        except Exception:
            pass
        return None
    finally:
        if own_session:
            session.close()
