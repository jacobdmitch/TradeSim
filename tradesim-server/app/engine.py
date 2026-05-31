"""One full trading cycle: scan -> score -> recommend -> (maybe) execute.

Mirrors TradeSimModel.scan() from the iOS app, with server-side safety:
a master kill switch and a balance floor, both enforced before any order.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from . import config, market
from .broker import Broker, TradeResult
from .db import (
    Portfolio, Recommendation, ScanLog, Settings, SessionLocal,
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


def run_once() -> CycleResult:
    init_db()
    session = SessionLocal()
    try:
        settings: Settings = get_settings(session)
        pf: Portfolio = get_portfolio(session)

        strategy = config.StrategyConfig()
        rotation = config.RotationConfig()
        predictor = Predictor(strategy, rotation)

        # --- Market scan ---
        products = market.fetch_usd_products()
        stats = market.fetch_stats(products)
        if not stats:
            raise RuntimeError("No market stats returned.")

        stats_by_base = {s.base: s for s in stats}

        # Mark current position to the latest price.
        if pf.has_position and pf.pos_base in stats_by_base:
            pf.pos_mark_price = stats_by_base[pf.pos_base].last

        # Seed the starting DIMO holding once.
        broker = Broker(dry_run=settings.dry_run)
        if not settings.seeded and config.SEED_BASE in stats_by_base:
            seed_stat = stats_by_base[config.SEED_BASE]
            broker.seed(pf, config.SEED_BASE, seed_stat.product_id,
                        settings.starting_balance, seed_stat.last)
            settings.seeded = True

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
        last_rec = (
            session.query(Recommendation).order_by(Recommendation.id.desc()).first()
        )
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

        # --- Execution gate ---
        if rec.action != "HOLD":
            allowed, reason = _execution_allowed(settings, pf, rec)
            if allowed and changed:
                executed = _execute(broker, rec, pf, stats_by_base, session, settings)
                note_parts.append(f"executed={[t.action for t in executed]}")
            else:
                note_parts.append(f"not_executed:{reason}")

        note = " ".join(note_parts)
        session.add(ScanLog(candidates=len(scored), note=note))
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
            order_id=tr.order_id,
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
            record(broker.exit(pf, sell_stat.last))
            record(broker.enter(pf, rec.to_base, buy_stat.product_id, buy_stat.last))

    return results
