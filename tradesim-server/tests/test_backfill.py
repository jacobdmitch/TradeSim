"""One-off ledger repair for the two LIVE incidents whose trades executed on
Coinbase but were never recorded (see db._backfill_unrecorded_trades)."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import db, web
from app.db import ScanLog, Trade


def _t(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


def _seed_production_like(session):
    """The rows the live database holds around both incidents."""
    session.add_all([
        Trade(ts=_t(2026, 10, 19, 0, 1, 11), action="BUY", base="INJ", price=8.713, quantity=15.91,
              cash_flow=-139.87144447, fee_usd=1.24761447, mode="LIVE",
              order_id="89992203-4bdf-4044-9dec-488c0aa8b200"),
        Trade(ts=_t(2026, 10, 19, 16, 45, 26), action="SELL", base="ZEC", price=1137.86,
              quantity=0.11290022, cash_flow=127.30846253023721, realized_pnl=-1.2826300453627795,
              fee_usd=1.1561817989628, mode="LIVE", order_id="b1a0f4db-6761-43c5-bd67-7833c095f4e5"),
        Trade(ts=_t(2026, 10, 20, 15, 15, 36), action="BUY", base="VVV", price=25.6219, quantity=4.898,
              cash_flow=-126.6255307958, fee_usd=1.1294645958, mode="LIVE",
              order_id="c9bd9c35-9235-49e1-80a6-8246367da0eb"),
        Trade(ts=_t(2026, 10, 20, 21, 16, 8), action="BUY", base="PUMP", price=0.0048389635585835,
              quantity=25246, cash_flow=-123.263954266, fee_usd=1.099480266, mode="LIVE",
              order_id="b686589b-d3f0-4304-bf8b-2a007d7aa040"),
        Trade(ts=_t(2026, 10, 21, 2, 15, 59), action="SELL", base="PUMP", price=0.00473529,
              quantity=25246, cash_flow=118.47120715794, realized_pnl=-4.792747108059999,
              fee_usd=1.07592418206, mode="LIVE", order_id="03f4f2ff-033e-454c-8bde-9dad63974b70"),
        ScanLog(ts=_t(2026, 10, 19, 2, 16, 25), candidates=0, note="error", error="404", trace_id="a" * 32),
        ScanLog(ts=_t(2026, 10, 20, 19, 15, 35), candidates=0, note="error", error="Order x", trace_id="b" * 32),
    ])
    session.commit()


def _by_marker(session):
    return {t.order_id: t for t in session.query(Trade).filter(Trade.order_id.like("est:backfill-%"))}


def test_backfill_records_the_three_missing_trades_from_exact_balances(session):
    _seed_production_like(session)
    db._backfill_unrecorded_trades()
    rows = _by_marker(session)
    assert set(rows) == {"est:backfill-2026-10-19-inj-sell", "est:backfill-2026-10-19-zec-buy",
                         "est:backfill-2026-10-20-vvv-sell"}

    inj, zec, vvv = (rows["est:backfill-2026-10-19-inj-sell"], rows["est:backfill-2026-10-19-zec-buy"],
                     rows["est:backfill-2026-10-20-vvv-sell"])
    assert (inj.action, inj.base, inj.quantity, inj.mode) == ("SELL", "INJ", 15.91, "LIVE")
    assert (zec.action, zec.base, zec.quantity) == ("BUY", "ZEC", 0.11290022)
    assert (vvv.action, vvv.base, vvv.quantity) == ("SELL", "VVV", 4.898)

    # Cash identities are exact: the USD balance went 0.02753 -> 0.01369 across the two legs.
    assert zec.cash_flow == pytest.approx(-(inj.cash_flow + 0.027533692844097284 - 0.013691504000897284))
    assert vvv.cash_flow == pytest.approx(123.2667897908381 - 0.6966232384380973)
    # P&L is net proceeds minus the cash paid for the position.
    assert inj.realized_pnl == pytest.approx(inj.cash_flow - 139.87144447)
    assert vvv.realized_pnl == pytest.approx(vvv.cash_flow - 126.6255307958)
    assert zec.realized_pnl is None
    # Price and fee are estimates built on the 0.9% rate seen on every recorded LIVE fill.
    assert zec.fee_usd == pytest.approx(-zec.cash_flow * 0.009 / 1.009)
    assert vvv.fee_usd == pytest.approx(vvv.cash_flow / 0.991 * 0.009)
    assert zec.price == pytest.approx(1181.84, abs=0.01)
    # Linked to the cycle that failed.
    assert inj.trace_id == zec.trace_id == "a" * 32 and vvv.trace_id == "b" * 32


def test_backfill_restates_the_zec_exit_against_what_was_really_paid(session):
    _seed_production_like(session)
    db._backfill_unrecorded_trades()
    zec_buy = _by_marker(session)["est:backfill-2026-10-19-zec-buy"]
    zec_sell = session.query(Trade).filter(Trade.order_id.like("b1a0f4db%")).one()
    assert zec_sell.realized_pnl == pytest.approx(127.30846253023721 + zec_buy.cash_flow)
    assert zec_sell.realized_pnl < -7


def test_ledger_now_matches_the_account(session):
    """Realized P&L over the four incident trades equals the cash that really
    left the account across them (INJ buy -> ... -> VVV sell, PUMP excluded)."""
    _seed_production_like(session)
    before = sum(t.realized_pnl or 0 for t in session.query(Trade))
    db._backfill_unrecorded_trades()
    after = sum(t.realized_pnl or 0 for t in session.query(Trade))
    # INJ sale -5.25, ZEC restatement -6.04, VVV sale -4.06
    assert after - before == pytest.approx(-5.25442069 - 6.03977339 - 4.05536424, abs=1e-4)


def test_backfill_is_idempotent_and_survives_the_pnl_migration(session):
    _seed_production_like(session)
    db._backfill_unrecorded_trades()
    snapshot = [(t.order_id, t.cash_flow, t.realized_pnl, t.fee_usd) for t in session.query(Trade).order_by(Trade.id)]
    db._backfill_unrecorded_trades()
    db._fix_live_realized_pnl()
    session.expire_all()
    assert [(t.order_id, t.cash_flow, t.realized_pnl, t.fee_usd)
            for t in session.query(Trade).order_by(Trade.id)] == snapshot


def test_backfill_does_nothing_on_a_database_without_those_trades(session):
    db._backfill_unrecorded_trades()
    assert session.query(Trade).count() == 0


def test_recent_trades_are_ordered_by_time_not_insert_order(session):
    _seed_production_like(session)
    db._backfill_unrecorded_trades()
    client = TestClient(web.app, follow_redirects=False)
    ts = [t["ts"] for t in client.get("/api/state").json()["trades"]]
    assert ts == sorted(ts, reverse=True)
