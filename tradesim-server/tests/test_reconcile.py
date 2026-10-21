"""Live reconciliation: adopting a chosen holding (any coin or USD) as the
starting point, in-place reconcile, and flagging holdings the bot isn't tracking."""
import pytest
from sqlalchemy import inspect, text

from app import config, db, engine
from app.db import get_portfolio, get_settings

from conftest import stat


class FakeBroker:
    def __init__(self, balances: dict):
        self._balances = balances

    def balances(self) -> dict:
        return dict(self._balances)


STATS = {"ZEC": stat("ZEC", 266.0), "INJ": stat("INJ", 8.5), "DIMO": stat("DIMO", 0.05)}


def _live(session, *, seeded: bool, adopt_base=None):
    st = get_settings(session)
    st.dry_run, st.seeded, st.adopt_base = False, seeded, adopt_base
    return st, get_portfolio(session)


def test_go_live_adopts_the_picked_coin_and_baselines_on_it(session):
    st, pf = _live(session, seeded=False, adopt_base="ZEC")
    engine._reconcile_live(FakeBroker({"USD": 0.01, "ZEC": 0.5}), pf, st, STATS)
    assert (pf.pos_base, pf.pos_product_id) == ("ZEC", "ZEC-USD")
    assert pf.pos_quantity == 0.5 and pf.pos_mark_price == 266.0
    assert pf.pos_cost_basis_usd == pytest.approx(133.0)  # basis = value at takeover
    assert pf.pos_peak_price == 266.0 and pf.pos_opened_at is not None
    assert st.seeded is True and st.adopt_base is None
    assert st.starting_balance == pytest.approx(133.01)


def test_go_live_with_usd_ignores_coin_holdings(session):
    st, pf = _live(session, seeded=False, adopt_base="USD")
    notes = engine._reconcile_live(FakeBroker({"USD": 40.0, "ZEC": 0.5}), pf, st, STATS)
    assert pf.pos_base is None
    assert st.starting_balance == pytest.approx(40.0)
    assert any(n.startswith("untracked:ZEC") for n in notes)


def test_go_live_drops_a_stale_paper_position_from_the_baseline(session):
    """A DRY-RUN holding must not leak into the real starting balance."""
    st, pf = _live(session, seeded=False, adopt_base="USD")
    pf.pos_base, pf.pos_quantity, pf.pos_mark_price = "INJ", 100.0, 8.5
    engine._reconcile_live(FakeBroker({"USD": 40.0}), pf, st, STATS)
    assert pf.pos_base is None
    assert st.starting_balance == pytest.approx(40.0)


def test_go_live_without_a_pick_keeps_the_legacy_seed_coin(session):
    st, pf = _live(session, seeded=False)
    engine._reconcile_live(FakeBroker({"USD": 1.0, config.SEED_BASE: 100.0}), pf, st, STATS)
    assert pf.pos_base == config.SEED_BASE
    assert st.starting_balance == pytest.approx(1.0 + 100.0 * 0.05)


def test_go_live_pick_with_no_balance_is_reported_not_silent(session):
    st, pf = _live(session, seeded=False, adopt_base="ZEC")
    notes = engine._reconcile_live(FakeBroker({"USD": 25.0}), pf, st, STATS)
    assert pf.pos_base is None
    assert "adopt_failed:ZEC" in notes
    assert st.adopt_base is None and st.seeded is True
    assert st.starting_balance == pytest.approx(25.0)


def test_reconcile_in_place_keeps_baseline_and_history(session):
    """The recovery path for the incident: bot believes it is in cash, the account
    holds ZEC. Adopt it without re-baselining or hiding history."""
    st, pf = _live(session, seeded=True, adopt_base="ZEC")
    st.starting_balance = 161.05
    marker = db._now()
    st.history_since = marker
    pf.cash = 0.0137
    engine._reconcile_live(FakeBroker({"USD": 0.0137, "ZEC": 0.5}), pf, st, STATS)
    assert pf.pos_base == "ZEC" and pf.pos_quantity == 0.5
    assert pf.total_value == pytest.approx(133.0137)
    assert st.adopt_base is None
    assert st.starting_balance == 161.05
    assert st.history_since == marker


def test_reconcile_in_place_to_the_coin_already_tracked_keeps_its_basis(session):
    st, pf = _live(session, seeded=True, adopt_base="ZEC")
    pf.pos_base, pf.pos_product_id, pf.pos_quantity = "ZEC", "ZEC-USD", 0.5
    pf.pos_cost_basis_usd, pf.pos_mark_price = 140.0, 250.0
    engine._reconcile_live(FakeBroker({"USD": 0.0, "ZEC": 0.5}), pf, st, STATS)
    assert pf.pos_cost_basis_usd == 140.0
    assert st.adopt_base is None


def test_untracked_holdings_are_flagged_but_never_adopted_on_their_own(session):
    st, pf = _live(session, seeded=True)
    notes = engine._reconcile_live(FakeBroker({"USD": 0.01, "ZEC": 0.5}), pf, st, STATS)
    assert pf.pos_base is None
    assert notes == ["untracked:ZEC($133)"]


def test_dust_and_unpriced_assets_are_not_flagged(session):
    st, pf = _live(session, seeded=True)
    notes = engine._reconcile_live(
        FakeBroker({"USD": 5.0, "ZEC": 0.0001, "USDC": 50.0, "OBSCURE": 10.0}), pf, st, STATS)
    assert notes == []


def test_a_vanished_tracked_position_is_cleared(session):
    st, pf = _live(session, seeded=True)
    pf.pos_base, pf.pos_product_id, pf.pos_quantity = "INJ", "INJ-USD", 15.0
    pf.pos_cost_basis_usd, pf.pos_mark_price = 130.0, 8.5
    engine._reconcile_live(FakeBroker({"USD": 0.01}), pf, st, STATS)
    assert pf.pos_base is None and pf.pos_quantity == 0.0
    assert pf.total_value == pytest.approx(0.01)


def test_run_once_adopts_the_pick_and_reports_the_rest(session, monkeypatch):
    """Whole cycle, LIVE: the wiring from request to portfolio, equity snapshot and scan note."""
    st, pf = _live(session, seeded=True, adopt_base="ZEC")
    st.starting_balance = 161.05
    session.commit()
    monkeypatch.setattr(engine.market, "fetch_usd_products", lambda: [])
    monkeypatch.setattr(engine.market, "fetch_stats", lambda products: list(STATS.values()))
    monkeypatch.setattr(engine.market, "fetch_series_for", lambda ids: {})
    monkeypatch.setattr(engine, "Broker",
                        lambda dry_run: FakeBroker({"USD": 0.01, "ZEC": 0.5, "INJ": 2.0}))

    assert engine.run_once(force=True).ok

    with db.SessionLocal() as fresh:
        assert get_portfolio(fresh).pos_base == "ZEC"
        eq = fresh.query(db.EquitySnapshot).order_by(db.EquitySnapshot.id.desc()).first()
        assert (eq.holding, round(eq.total_value, 2)) == ("ZEC", 133.01)
        scan = fresh.query(db.ScanLog).order_by(db.ScanLog.id.desc()).first()
        assert "untracked:INJ($17)" in scan.note
        assert get_settings(fresh).adopt_base is None


def test_adopt_base_column_is_added_to_an_existing_database(session):
    with db.ENGINE.begin() as conn:
        conn.execute(text("ALTER TABLE settings DROP COLUMN adopt_base"))
    db.ENGINE.dispose()  # SQLite connections keep a stale schema view after DDL
    assert "adopt_base" not in {c["name"] for c in inspect(db.ENGINE).get_columns("settings")}
    db._run_migrations()
    assert "adopt_base" in {c["name"] for c in inspect(db.ENGINE).get_columns("settings")}


def test_mode_switch_records_the_pick_and_clears_it_going_dry(session):
    db.reset_for_mode_switch(session, to_live=True, adopt_base="ZEC")
    st = get_settings(session)
    assert (st.seeded, st.adopt_base) == (False, "ZEC")
    db.reset_for_mode_switch(session, to_live=False)
    assert get_settings(session).adopt_base is None
