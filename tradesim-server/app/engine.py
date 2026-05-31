"""One full trading cycle: scan -> score -> recommend -> (maybe) execute.

Mirrors TradeSimModel.scan() from the iOS app, with server-side safety:
a master kill switch and a balance floor, both enforced before any order.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from . import auditor, config, market
from .broker import Broker, TradeResult
from .db import (
    AuditLog, EquitySnapshot, Portfolio, Recommendation, ScanLog, Settings, SessionLocal,
    get_portfolio, get_settings, init_db,
)
from .predictor import CoinScore, Predictor, Recommendation as Rec, select_candidates

log = logging.getLogger("tradesim.engine")


@dataclass
class CycleResult:
    ok: bool
    recommendation: Optional[Rec]
    executed: List[TradeResult]
    candidates: int
    note: str
    error: Optional[str] = None


def run_once(force: bool = False) -> CycleResult:
    init_db()
    session = SessionLocal()
    try:
        settings: Settings = get_settings(session)
        pf: Portfolio = get_portfolio(session)

        # --- Cadence gate: throttle the 15-min cron to the chosen interval ---
        if not force:
            last = session.query(ScanLog).order_by(ScanLog.id.desc()).first()
            if last is not None and last.ts is not None:
                last_ts = last.ts if last.ts.tzinfo else last.ts.replace(tzinfo=timezone.utc)
                elapsed_min = (datetime.now(timezone.utc) - last_ts).total_seconds() / 60
                interval = getattr(settings, "interval_minutes", config.INTERVAL_MINUTES_DEFAULT)
                if elapsed_min < interval - (config.CRON_GRANULARITY_MIN / 2):
                    return CycleResult(True, None, [], 0,
                                       f"skipped: {elapsed_min:.0f}/{interval}min cadence")

        strategy = config.StrategyConfig()
        rotation = config.RotationConfig()
        predictor = Predictor(strategy, rotation)

        # --- Market scan ---
        products = market.fetch_usd_products()
        stats = market.fetch_stats(products)
        if not stats:
            raise RuntimeError("No market stats returned.")

        stats_by_base = {s.base: s for s in stats}
        broker = Broker(dry_run=settings.dry_run)

        if settings.dry_run:
            # Paper mode: mark to last price, seed the modeled starting stake once.
            if pf.has_position and pf.pos_base in stats_by_base:
                pf.pos_mark_price = stats_by_base[pf.pos_base].last
            if not settings.seeded and config.SEED_BASE in stats_by_base:
                seed_stat = stats_by_base[config.SEED_BASE]
                broker.seed(pf, config.SEED_BASE, seed_stat.product_id,
                            settings.starting_balance, seed_stat.last)
                settings.seeded = True
        else:
            # LIVE mode: trust the real Coinbase account, not modeled values.
            # If balances can't be read, abort the cycle rather than trade blind.
            _reconcile_live(broker, pf, settings, stats_by_base)

        # Candidates -> deep analysis on those with enough candles.
        candidates = select_candidates(stats, rotation, config.MIN_LIQUIDITY_USD,
                                        pf.pos_base, config.SEED_BASE)
        closes_map = market.fetch_closes_for([c.product_id for c in candidates])
        scored: List[CoinScore] = []
        for stat in candidates:
            closes = closes_map.get(stat.product_id)
            if closes and len(closes) > strategy.long_sma + 1:
                scored.append(predictor.score(stat, closes))
        ranked = predictor.rank(scored)

        rec = predictor.recommend(ranked, pf.pos_base, config.FEE_RATE)

        # Persist the recommendation only when it changes (matches the app).
        # Scope to the current run so the first cycle after a mode switch always
        # records a fresh recommendation.
        rec_q = session.query(Recommendation)
        if settings.history_since:
            rec_q = rec_q.filter(Recommendation.ts >= settings.history_since)
        last_rec = rec_q.order_by(Recommendation.id.desc()).first()
        changed = not (
            last_rec
            and last_rec.action == rec.action
            and last_rec.from_base == rec.from_base
            and last_rec.to_base == rec.to_base
        )
        if changed:
            session.add(Recommendation(
                action=rec.action, from_base=rec.from_base, to_base=rec.to_base,
                rationale=rec.rationale, edge_pct=rec.edge_pct,
            ))

        executed: List[TradeResult] = []
        note_parts = [f"mode={'DRY' if settings.dry_run else 'LIVE'}",
                      f"enabled={settings.enabled}"]

        # 2-scan confirmation: ENTER/ROTATE must persist across two consecutive
        # scans before acting (kills single-cycle whipsaw). EXIT acts immediately
        # so a protective move to cash isn't delayed.
        sig = f"{rec.action}|{rec.from_base}|{rec.to_base}"
        persisted = (settings.prev_rec_sig == sig)
        needs_confirm = rec.action in {"ENTER", "ROTATE"}

        # --- Execution gate ---
        if rec.action != "HOLD":
            allowed, reason = _execution_allowed(settings, pf, rec)
            hold_block, hold_remaining = _within_min_hold(pf, settings)
            if not allowed:
                note_parts.append(f"not_executed:{reason}")
            elif rec.action == "ROTATE" and hold_block:
                note_parts.append(f"min_hold:{hold_remaining:.1f}h_left")
            elif needs_confirm and not persisted:
                note_parts.append("awaiting_confirmation:1of2")
            else:
                # Optional Claude pre-trade audit (veto-only, fail-open).
                audit_res = _run_audit(rec, ranked, pf, stats_by_base, settings, session)
                if audit_res is not None and audit_res.used and not audit_res.approved:
                    note_parts.append(f"audit_veto:{audit_res.reason[:80]}")
                else:
                    executed = _execute(broker, rec, pf, stats_by_base, session, settings)
                    note_parts.append(f"executed={[t.action for t in executed]}")

        # Remember this scan's recommendation for next time's confirmation check.
        settings.prev_rec_sig = sig

        note = " ".join(note_parts)
        # Persist the ranked candidates so the dashboard can show what the scan
        # weighed (best-first by predicted edge after fees).
        cand_payload = [
            {"base": c.base, "edge": round(c.predicted_edge_pct, 4),
             "momentum": round(c.momentum, 4),
             "rsi": round(c.rsi, 1) if c.rsi is not None else None,
             "change_24h": round(c.change_24h, 4), "trend_up": c.trend_up}
            for c in ranked
        ]
        session.add(ScanLog(candidates=len(scored), note=note,
                            candidates_json=json.dumps(cand_payload)))
        session.add(EquitySnapshot(
            total_value=pf.total_value, cash=pf.cash,
            position_value=pf.position_value, holding=pf.pos_base or "USD",
        ))
        session.commit()
        return CycleResult(True, rec, executed, len(scored), note)

    except Exception as e:  # noqa: BLE001 - log and record, never crash the cron
        log.exception("cycle failed")
        try:
            session.rollback()
            session.add(ScanLog(candidates=0, note="error", error=str(e)))
            session.commit()
        except Exception:
            pass
        return CycleResult(False, None, [], 0, "error", str(e))
    finally:
        session.close()


def _reconcile_live(broker: Broker, pf: Portfolio, settings: Settings, stats_by_base) -> None:
    """LIVE only: overwrite the portfolio bookkeeping with the actual Coinbase
    balances so trade sizing, account value, and P&L reflect real funds — never
    the modeled $seed. Raises on balance-read failure so the cycle aborts instead
    of trading on stale numbers."""
    try:
        bals = broker.balances()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"live balance read failed; skipping cycle: {e}")

    pf.cash = bals.get("USD", 0.0)

    # First live cycle: adopt whatever the account actually holds (your DIMO),
    # and anchor the return baseline to that real starting value.
    if not settings.seeded:
        seed_qty = bals.get(config.SEED_BASE, 0.0)
        st = stats_by_base.get(config.SEED_BASE)
        if seed_qty > 0 and st and st.last > 0:
            pf.pos_base = config.SEED_BASE
            pf.pos_product_id = st.product_id
            pf.pos_quantity = seed_qty
            pf.pos_mark_price = st.last
            pf.pos_cost_basis_usd = seed_qty * st.last  # basis = value at takeover (PnL starts at 0)
            pf.pos_opened_at = datetime.now(timezone.utc)
        settings.seeded = True
        settings.starting_balance = pf.total_value  # real baseline for return %

    # Reconcile the tracked position to the real on-exchange balance + price.
    if pf.pos_base:
        real_qty = bals.get(pf.pos_base, 0.0)
        st = stats_by_base.get(pf.pos_base)
        if st:
            pf.pos_mark_price = st.last
        if real_qty > 0:
            pf.pos_quantity = real_qty
        else:
            # Position no longer on the exchange — treat as cash only.
            pf.pos_base = None
            pf.pos_product_id = None
            pf.pos_quantity = 0.0
            pf.pos_cost_basis_usd = 0.0
            pf.pos_mark_price = 0.0


def _run_audit(rec: Rec, ranked: List[CoinScore], pf: Portfolio, stats_by_base,
               settings: Settings, session):
    """Run the optional Claude audit and log the verdict. Returns AuditResult or None."""
    if not getattr(settings, "audit_enabled", False):
        return None

    def score_for(base):
        return next((s for s in ranked if s.base == base), None)

    def snap(base):
        sc = score_for(base)
        st = stats_by_base.get(base)
        if not st:
            return None
        return {
            "base": base,
            "price": round(st.last, 8),
            "change_24h_pct": round(st.change_pct, 2),
            "volume_usd_24h": round(st.volume_usd, 0),
            "momentum_pct": round(sc.momentum, 2) if sc else None,
            "rsi": round(sc.rsi, 1) if sc and sc.rsi is not None else None,
            "trend_up": sc.trend_up if sc else None,
            "predicted_edge_pct": round(sc.predicted_edge_pct, 2) if sc else None,
        }

    payload = {
        "action": rec.action,
        "rationale": rec.rationale,
        "fee_per_leg_pct": config.FEE_RATE * 100,
        "target": snap(rec.to_base) if rec.to_base else None,
        "current_holding": snap(rec.from_base) if rec.from_base else None,
    }
    res = auditor.audit(rec.action, rec.to_base, rec.from_base, payload,
                        audit_enabled=True)
    if res.used:
        session.add(AuditLog(
            action=rec.action, to_base=rec.to_base,
            verdict="VETO" if not res.approved else "APPROVE",
            reason=res.reason[:500], model=res.model,
        ))
    return res


def _within_min_hold(pf: Portfolio, settings: Settings) -> tuple[bool, float]:
    """(blocked, hours_remaining) — True if the position is younger than the
    minimum hold. Used only to block coin->coin ROTATE churn, never EXIT."""
    opened = getattr(pf, "pos_opened_at", None)
    min_h = getattr(settings, "min_hold_hours", config.MIN_HOLD_HOURS_DEFAULT)
    if not pf.pos_base or opened is None or min_h <= 0:
        return False, 0.0
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - opened).total_seconds() / 3600
    return (age_h < min_h), max(min_h - age_h, 0.0)


def _execution_allowed(settings: Settings, pf: Portfolio, rec: Rec) -> tuple[bool, str]:
    if not settings.enabled:
        return False, "kill_switch_off"
    # Balance floor halts new deployments/rotations but still permits a protective EXIT.
    if rec.action in {"ENTER", "ROTATE"} and pf.total_value <= settings.balance_floor_usd:
        return False, "below_balance_floor"
    return True, "ok"


def _execute(broker: Broker, rec: Rec, pf: Portfolio, stats_by_base, session, settings) -> List[TradeResult]:
    results: List[TradeResult] = []

    def record(tr: Optional[TradeResult]):
        if tr is None:
            return
        from .db import Trade
        session.add(Trade(
            action=tr.action, base=tr.base, price=tr.price, quantity=tr.quantity,
            cash_flow=tr.cash_flow, realized_pnl=tr.realized_pnl, mode=tr.mode,
            order_id=tr.order_id, fee_usd=tr.fee_usd,
        ))
        results.append(tr)

    if rec.action == "ENTER" and rec.to_base in stats_by_base:
        s = stats_by_base[rec.to_base]
        record(broker.enter(pf, rec.to_base, s.product_id, s.last))

    elif rec.action == "EXIT" and pf.has_position:
        s = stats_by_base.get(pf.pos_base)
        if s:
            record(broker.exit(pf, s.last))

    elif rec.action == "ROTATE" and pf.has_position and rec.to_base in stats_by_base:
        sell_stat = stats_by_base.get(pf.pos_base)
        buy_stat = stats_by_base[rec.to_base]
        if sell_stat and pf.pos_base != rec.to_base:
            _rotate_cheapest(broker, pf, sell_stat, buy_stat, settings, record)

    return results


def _rotate_cheapest(broker, pf, sell_stat, buy_stat, settings, record) -> None:
    """Rotate the position into the target via whichever path keeps more value:
    a single Coinbase Convert, or two order-book legs (sell->USD->buy).

    Two-leg keeps (1-fee)^2 of value. Convert keeps to_qty*buy_price / position
    value, inclusive of Coinbase's convert spread+fee. We only use Convert (LIVE
    only) when a real quote says it keeps strictly more, and a confirmed commit
    succeeds; otherwise we fall back to the two legs."""
    fee = broker.fee_rate
    two_leg_keep = (1 - fee) ** 2

    def two_leg():
        record(broker.exit(pf, sell_stat.last))
        record(broker.enter(pf, buy_stat.base, buy_stat.product_id, buy_stat.last))

    # Convert is a real-money, live-only path.
    if settings.dry_run:
        return two_leg()

    from_qty = pf.pos_quantity
    in_value = from_qty * sell_stat.last
    quote = broker.convert_quote(pf.pos_base, buy_stat.base, from_qty)
    convert_keep = None
    if quote and in_value > 0 and quote.to_qty > 0:
        convert_keep = (quote.to_qty * buy_stat.last) / in_value

    use_convert = (
        convert_keep is not None and convert_keep > two_leg_keep and convert_keep <= 1.02
    )
    if not use_convert:
        log.info("rotation route=two_leg (convert_keep=%s two_leg_keep=%.4f)", convert_keep, two_leg_keep)
        return two_leg()

    # Commit the convert; only book it if Coinbase confirms it settled.
    realized_to = broker.convert_commit(quote)
    if not realized_to or realized_to <= 0:
        # Uncertain outcome: do NOT also place orders (avoid double execution).
        # Next live cycle reconciles from real balances and retries if needed.
        log.warning("convert commit unconfirmed; skipping rotation this cycle")
        return

    out_value = realized_to * buy_stat.last
    cost_basis = pf.pos_cost_basis_usd
    convert_cost = max(in_value - out_value, 0.0)  # spread+fee baked into the convert
    tid = f"convert:{quote.trade_id}"
    # Book the closed leg (realized P&L vs basis) and the opened leg, no USD touched.
    record(TradeResult("SELL", sell_stat.base, sell_stat.last, from_qty,
                       out_value, out_value - cost_basis, "LIVE", tid, fee_usd=convert_cost))
    pf.pos_base = buy_stat.base
    pf.pos_product_id = buy_stat.product_id
    pf.pos_quantity = realized_to
    pf.pos_cost_basis_usd = out_value
    pf.pos_mark_price = buy_stat.last
    pf.pos_opened_at = datetime.now(timezone.utc)
    record(TradeResult("BUY", buy_stat.base, buy_stat.last, realized_to,
                       -out_value, None, "LIVE", tid, fee_usd=0.0))
    log.info("rotation route=convert (keep=%.4f > %.4f)", convert_keep, two_leg_keep)
