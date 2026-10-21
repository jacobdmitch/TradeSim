"""Fast trailing-stop guard.

The 15-minute trading cycle used to be the only thing that checked the trailing stop, so
a coin that fell fast could fall far past it before the next look (2026-10-21: DOOD was
2% down at the 15:30 cycle and sold at the 15:45 one 26% lower; its 15% stop was first
touched at 15:36). This module re-checks the stop for the held coin every
GUARD_INTERVAL_SECONDS against the live exchange ticker and sells at once when it is hit.

It runs as a thread in the dashboard web process: always on, already holds the Coinbase
key, and needs no extra service. It uses the same stop as the cycle (the peak since entry
and the volatility-scaled distance the cycle stores in portfolio.pos_stop_pct), only
trades LIVE with trading ON, and shares db.trading_lock with the cycle so the two never
act at the same moment.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import config, market
from .broker import Broker
from .db import (
    Recommendation, SessionLocal, get_portfolio, get_settings, get_strategy_params, trading_lock,
)
from .engine import _scaled_trailing_stop_pct, _trade_row

log = logging.getLogger("tradesim.guard")

CONFIRM_PASSES = 2                       # consecutive passes under the stop before selling
HEARTBEAT_EVERY = timedelta(seconds=60)  # how often guard_checked_at is rewritten

_state = {"cooldown_until": 0.0, "below": 0, "prev": (None, 0.0)}  # prev = (product, last price)
_thread: Optional[threading.Thread] = None


def _make_broker() -> Broker:
    return Broker(dry_run=False)


def check_once() -> str:
    """One pass. Returns a short status: idle, skipped, cooldown, holding, waiting, stopped
    or exit_failed (for logs and tests)."""
    with trading_lock(timeout=0) as got:
        if not got:
            return "skipped: a cycle is running"
        if time.monotonic() < _state["cooldown_until"]:
            return "cooldown: the last sale attempt failed"
        with SessionLocal() as s:
            st, pf = get_settings(s), get_portfolio(s)
            now = datetime.now(timezone.utc)
            if st.dry_run or not st.enabled or not pf.has_position:
                _beat(s, st, now)
                _state.update(below=0, prev=(None, 0.0))
                why = "dry-run" if st.dry_run else "trading off" if not st.enabled else "no position"
                return f"idle: {why}"
            price = market.fetch_last_price(pf.pos_product_id)
            _beat(s, st, now)
            if not price:
                return "skipped: no price"

            # A new high only counts once two passes in a row agree (the lower of the two), so a
            # stray print on a thin book can't ratchet the stop up and then sell a healthy position.
            prev_product, prev_price = _state["prev"]
            confirmed = min(price, prev_price) if prev_product == pf.pos_product_id else 0.0
            _state["prev"] = (pf.pos_product_id, price)
            peak = max(pf.pos_peak_price or 0.0, confirmed)
            if peak > (pf.pos_peak_price or 0.0):
                pf.pos_peak_price = peak
                s.commit()
            stop_pct = pf.pos_stop_pct or _scaled_trailing_stop_pct(get_strategy_params(s).trailing_stop_pct, 0.0)
            stop_price = peak * (1 - stop_pct / 100)
            if price > stop_price:
                _state["below"] = 0
                return "holding"
            _state["below"] += 1
            if _state["below"] < CONFIRM_PASSES:
                return (f"waiting: {pf.pos_base} at {price:.8g} is under its stop {stop_price:.8g}; "
                        "confirming on the next pass")
            return _sell(s, pf, price, peak, stop_pct)


def _beat(s, st, now: datetime) -> None:
    last = st.guard_checked_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last is None or now - last >= HEARTBEAT_EVERY:
        st.guard_checked_at = now
        s.commit()


def _sell(s, pf, price: float, peak: float, stop_pct: float) -> str:
    base = pf.pos_base
    off_peak = (price / peak - 1) * 100
    trace_id = uuid.uuid4().hex
    try:
        tr = _make_broker().exit(pf, price)
    except Exception as e:  # noqa: BLE001 - the next cycle re-syncs from the account
        s.rollback()
        _state["cooldown_until"] = time.monotonic() + config.GUARD_RETRY_SECONDS
        log.exception("fast guard: selling %s failed; backing off %.0fs", base, config.GUARD_RETRY_SECONDS)
        return f"exit_failed: {e}"
    _state.update(below=0, prev=(None, 0.0))
    if tr is None:
        return "idle: nothing to sell"
    s.add(_trade_row(tr, trace_id))
    s.add(Recommendation(
        action="EXIT", from_base=base, to_base=None, edge_pct=0.0, trace_id=trace_id,
        rationale=(f"Fast stop guard: {base} is {abs(off_peak):.1f}% below its peak since entry "
                   f"(stop at -{stop_pct:.1f}%, volatility-scaled). Sold between cycles."),
    ))
    s.commit()
    log.warning("fast guard sold %s at %.8g (%.1f%% below its peak)", base, price, abs(off_peak))
    return f"stopped: sold {base} at {price:.8g}"


def loop() -> None:
    """Run check_once forever; a failed pass is logged and the loop carries on."""
    log.warning("fast stop guard started (every %.0fs)", config.GUARD_INTERVAL_SECONDS)
    while True:
        try:
            check_once()
        except Exception:  # noqa: BLE001
            log.exception("fast stop guard pass failed")
        time.sleep(max(config.GUARD_INTERVAL_SECONDS, 5.0))


def start() -> None:
    """Start the guard thread once per process."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=loop, name="fast-stop-guard", daemon=True)
    _thread.start()
