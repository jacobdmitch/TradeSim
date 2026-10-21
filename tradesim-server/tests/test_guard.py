"""Fast stop guard: a trailing stop checked every few seconds between cycles.

Regression for 2026-10-21: DOOD was bought at 14:31 UTC, was only 2% down at the
15:30 cycle, and was sold at the next one (15:45) 26% lower. Replayed on 1-minute
candles, its 15% stop was first touched at 15:36."""
import threading
from types import SimpleNamespace

import pytest

from app import config, db, engine, guard, market
from app.broker import Broker, BrokerError, TradeResult
from app.db import Portfolio, Recommendation, Trade, get_portfolio, get_settings
from app.predictor import CoinScore, select_candidates, RotationConfig

from conftest import stat


@pytest.fixture(autouse=True)
def fresh_guard_state():
    guard._state.update(cooldown_until=0.0, below=0, prev=(None, 0.0))


class FakeBroker:
    def __init__(self, fail=False):
        self.fail, self.exits = fail, []

    def exit(self, pf, price):
        self.exits.append(price)
        if self.fail:
            raise BrokerError("exchange said no")
        base, qty = pf.pos_base, pf.pos_quantity
        proceeds = qty * price * 0.991
        tr = TradeResult("SELL", base, price, qty, proceeds, proceeds - pf.pos_cost_basis_usd, "LIVE",
                         "order-1", fee_usd=qty * price * 0.009)
        pf.cash += proceeds
        Broker._clear_position(pf)
        return tr


def _holding(session, *, dry_run=False, enabled=True, stop_pct=15.0, peak=0.00499):
    st = get_settings(session)
    st.dry_run, st.enabled = dry_run, enabled
    pf = get_portfolio(session)
    pf.cash, pf.pos_base, pf.pos_product_id = 0.0, "DOOD", "DOOD-USD"
    pf.pos_quantity, pf.pos_cost_basis_usd, pf.pos_mark_price = 26379.0, 118.47, 0.0045
    pf.pos_peak_price, pf.pos_stop_pct = peak, stop_pct
    session.commit()


def _prices(monkeypatch, *seq):
    """Successive ticker prices; a None entry is a failed lookup."""
    it = iter(seq)
    monkeypatch.setattr(guard.market, "fetch_last_price", lambda product_id: next(it))


def _broker(monkeypatch, **kw):
    b = FakeBroker(**kw)
    monkeypatch.setattr(guard, "_make_broker", lambda: b)
    return b


def _no_price(monkeypatch):
    def boom(product_id):
        raise AssertionError("the guard must not fetch a price when it has nothing to guard")
    monkeypatch.setattr(guard.market, "fetch_last_price", boom)


def _fresh(model):
    with db.SessionLocal() as s:
        return s.query(model).all()


def _pf():
    with db.SessionLocal() as s:
        return get_portfolio(s)


def _settings():
    with db.SessionLocal() as s:
        return get_settings(s)


# ---- when it does nothing ----

def test_idle_in_dry_run_when_trading_is_off_and_with_no_position(session, monkeypatch):
    _no_price(monkeypatch)
    _holding(session, dry_run=True)
    assert guard.check_once().startswith("idle")
    _holding(session, enabled=False)
    assert guard.check_once().startswith("idle")
    _holding(session)
    pf = get_portfolio(session)
    pf.pos_base, pf.pos_quantity = None, 0.0
    session.commit()
    assert guard.check_once().startswith("idle")


def test_skips_while_a_cycle_holds_the_trading_lock(session, monkeypatch):
    _holding(session)
    _no_price(monkeypatch)
    with db.trading_lock(timeout=0) as got:
        assert got
        assert guard.check_once().startswith("skipped")


def test_a_failed_price_lookup_is_skipped_not_fatal(session, monkeypatch):
    _holding(session)
    _prices(monkeypatch, None)
    assert guard.check_once().startswith("skipped")


# ---- the stop ----

def test_a_new_high_ratchets_the_peak_once_two_passes_agree(session, monkeypatch):
    _holding(session)
    broker = _broker(monkeypatch)
    _prices(monkeypatch, 0.0046, 0.0052, 0.0053)
    assert [guard.check_once() for _ in range(3)] == ["holding"] * 3
    assert _pf().pos_peak_price == pytest.approx(0.0052)         # min of the last two highs
    assert broker.exits == []


def test_one_stray_high_print_does_not_move_the_stop(session, monkeypatch):
    _holding(session)
    _broker(monkeypatch)
    _prices(monkeypatch, 0.0046, 0.0060, 0.0046)
    for _ in range(3):
        guard.check_once()
    assert _pf().pos_peak_price == pytest.approx(0.00499)


def test_sells_on_the_second_consecutive_pass_below_the_stop(session, monkeypatch):
    """The 2026-10-21 DOOD path (1-minute lows). Peak 0.00499, 15% stop at 0.004242."""
    _holding(session)
    broker = _broker(monkeypatch)
    _prices(monkeypatch, 0.00450, 0.00433, 0.00439, 0.00412, 0.00411)
    results = [guard.check_once() for _ in range(5)]
    assert results[:3] == ["holding"] * 3
    assert results[3].startswith("waiting")          # first pass below the stop: confirm once
    assert results[4].startswith("stopped")
    assert broker.exits == [0.00411]

    with db.SessionLocal() as s:
        (trade,) = s.query(Trade).all()
        assert (trade.action, trade.base, trade.mode) == ("SELL", "DOOD", "LIVE")
        rec = s.query(Recommendation).one()
        assert rec.action == "EXIT" and "Fast stop guard" in rec.rationale and "DOOD" in rec.rationale
        assert "is 17.6% below its peak" in rec.rationale          # not "-17.6%"
        pf = get_portfolio(s)
        assert pf.pos_base is None and pf.cash == pytest.approx(26379 * 0.00411 * 0.991)
    # about $107 against the $85 the 15-minute cycle got
    assert pf.cash > 100


def test_a_single_bad_print_does_not_sell(session, monkeypatch):
    _holding(session)
    broker = _broker(monkeypatch)
    _prices(monkeypatch, 0.00412, 0.00450, 0.00412, 0.00450)
    assert [guard.check_once().split(":")[0] for _ in range(4)] == ["waiting", "holding", "waiting", "holding"]
    assert broker.exits == []


def test_a_position_with_no_stored_stop_uses_the_strategy_baseline(session, monkeypatch):
    """Fresh from an older cycle: no pos_stop_pct yet. Baseline is trailing_stop_pct (5.0)."""
    _holding(session, stop_pct=0.0)
    broker = _broker(monkeypatch)
    _prices(monkeypatch, 0.00470, 0.00470)          # 5.8% under the peak, past a 5% stop
    assert guard.check_once().startswith("waiting")
    assert guard.check_once().startswith("stopped")
    assert broker.exits == [0.0047]


def test_a_failed_sale_changes_nothing_and_backs_off(session, monkeypatch):
    _holding(session)
    broker = _broker(monkeypatch, fail=True)
    clock = [1000.0]
    monkeypatch.setattr(guard.time, "monotonic", lambda: clock[0])
    _prices(monkeypatch, 0.0040, 0.0040, 0.0040, 0.0040)
    guard.check_once()                                   # first pass below the stop
    assert guard.check_once().startswith("exit_failed")
    assert _pf().pos_base == "DOOD" and _fresh(Trade) == []
    assert guard.check_once().startswith("cooldown") and len(broker.exits) == 1
    clock[0] += config.GUARD_RETRY_SECONDS + 1
    assert guard.check_once().startswith("exit_failed") and len(broker.exits) == 2


def test_heartbeat_is_recorded_and_not_rewritten_every_pass(session, monkeypatch):
    _holding(session)
    _broker(monkeypatch)
    _prices(monkeypatch, 0.0046, 0.0046)
    assert get_settings(session).guard_checked_at is None
    guard.check_once()
    first = _settings().guard_checked_at
    assert first is not None
    guard.check_once()
    assert _settings().guard_checked_at == first


def test_start_runs_one_daemon_thread(monkeypatch):
    started, release = threading.Event(), threading.Event()
    monkeypatch.setattr(guard, "loop", lambda: (started.set(), release.wait(5)))
    monkeypatch.setattr(guard, "_thread", None)
    guard.start()
    first = guard._thread
    guard.start()
    assert guard._thread is first and first.daemon
    assert started.wait(2)
    release.set()


# ---- the lock ----

def test_trading_lock_excludes_a_second_taker_and_releases(session):
    with db.trading_lock(timeout=0) as first:
        assert first
        with db.trading_lock(timeout=0) as second:
            assert not second
    with db.trading_lock(timeout=0) as again:
        assert again


def test_trading_lock_on_postgres_takes_and_releases_an_advisory_lock(monkeypatch):
    calls = []

    class Conn:
        def execute(self, stmt, params=None):
            calls.append(str(stmt))
            return SimpleNamespace(scalar=lambda: self.grant)

        def commit(self): pass
        def rollback(self): pass
        def close(self): calls.append("close")

    conn = Conn()
    conn.grant = True
    monkeypatch.setattr(db, "ENGINE", SimpleNamespace(dialect=SimpleNamespace(name="postgresql"),
                                                      connect=lambda: conn))
    with db.trading_lock(timeout=0) as got:
        assert got
    assert "pg_try_advisory_lock" in calls[0] and "pg_advisory_unlock" in calls[1] and calls[-1] == "close"

    calls.clear()
    conn.grant = False
    with db.trading_lock(timeout=0) as got:
        assert not got
    assert not any("pg_advisory_unlock" in c for c in calls) and calls[-1] == "close"


def test_a_cycle_that_cannot_get_the_lock_fails_visibly(session, monkeypatch):
    monkeypatch.setattr(engine, "LOCK_WAIT_SECONDS", 0)
    with db.trading_lock(timeout=0) as got:
        assert got
        result = engine.run_once(force=True)
    assert result.ok is False and "lock" in result.error


# ---- stop distance is stored by the cycle ----

def _score(base, atr):
    return CoinScore(product_id=f"{base}-USD", base=base, last=1.0, change_24h=0.0, momentum=1.0,
                     rsi=50.0, trend_up=True, predicted_edge_pct=1.0, atr_pct=atr)


def test_the_cycle_stores_the_volatility_scaled_stop_for_the_held_coin():
    pf = Portfolio(pos_base="DOOD", pos_quantity=1.0)
    engine._refresh_stop_pct(pf, [_score("BTC", 1.0), _score("DOOD", 6.0)], 4.4)
    assert pf.pos_stop_pct == pytest.approx(8.8)                  # 4.4 * 6.0 / 3.0
    engine._refresh_stop_pct(pf, [_score("DOOD", 40.0)], 4.4)
    assert pf.pos_stop_pct == pytest.approx(15.0)                 # ceiling
    engine._refresh_stop_pct(pf, [_score("BTC", 1.0)], 4.4)       # held coin not scored
    assert pf.pos_stop_pct == pytest.approx(4.4)
    flat = Portfolio(pos_base=None, pos_quantity=0.0, pos_stop_pct=7.0)
    engine._refresh_stop_pct(flat, [_score("BTC", 1.0)], 4.4)
    assert flat.pos_stop_pct == 0.0


# ---- entry filter: keep out of coins with an extreme 24h range ----

def _coin(base, volume_usd, high, low, last=1.0):
    s = stat(base, last)
    s.volume, s.high, s.low = volume_usd / last, high, low
    return s


def test_range_pct_is_the_24h_high_low_spread_over_price():
    assert _coin("X", 1e6, high=1.4, low=0.6).range_pct == pytest.approx(80.0)
    assert stat("Y", 2.0).range_pct == 0.0


def test_entry_candidates_skip_extreme_24h_ranges_but_keep_the_held_coin_and_btc():
    stats = [_coin("BTC", 5e8, 1.03, 0.98), _coin("ETH", 2e8, 1.05, 0.97),
             _coin("DOOD", 6e6, 1.4, 0.6),            # 80% range, the 2026-10-21 entry
             _coin("OK", 5e6, 1.2, 0.95)]
    picked = {s.base for s in select_candidates(stats, RotationConfig(), 100_000, None, "DIMO")}
    assert picked == {"BTC", "ETH", "OK"}
    held = {s.base for s in select_candidates(stats, RotationConfig(), 100_000, "DOOD", "DIMO")}
    assert "DOOD" in held                              # still scored so the bot can hold or exit it


def test_the_range_cap_is_configurable_and_can_be_switched_off(monkeypatch):
    stats = [_coin("BTC", 5e8, 1.03, 0.98), _coin("DOOD", 6e6, 1.4, 0.6)]
    monkeypatch.setattr(config, "MAX_24H_RANGE_PCT", 0)
    assert "DOOD" in {s.base for s in select_candidates(stats, RotationConfig(), 100_000, None, "DIMO")}
    monkeypatch.setattr(config, "MAX_24H_RANGE_PCT", 100)
    assert "DOOD" in {s.base for s in select_candidates(stats, RotationConfig(), 100_000, None, "DIMO")}
    monkeypatch.setattr(config, "MAX_24H_RANGE_PCT", 40)
    assert "DOOD" not in {s.base for s in select_candidates(stats, RotationConfig(), 100_000, None, "DIMO")}


# ---- ticker ----

def test_fetch_last_price_reads_the_exchange_ticker(monkeypatch):
    class Resp:
        def __init__(self, data, ok=True): self.data, self.ok = data, ok
        def raise_for_status(self):
            if not self.ok:
                raise RuntimeError("503")
        def json(self): return self.data
    seen = {}
    def fake_get(url, timeout):
        seen["url"] = url
        return Resp({"price": "0.00412", "bid": "0.0041"})
    monkeypatch.setattr(market._SESSION, "get", fake_get)
    assert market.fetch_last_price("DOOD-USD") == pytest.approx(0.00412)
    assert seen["url"].endswith("/products/DOOD-USD/ticker")
    monkeypatch.setattr(market._SESSION, "get", lambda url, timeout: Resp({}, ok=False))
    assert market.fetch_last_price("DOOD-USD") is None


# ---- dashboard ----

def _page():
    from fastapi.testclient import TestClient
    from app import web
    return TestClient(web.app, follow_redirects=False).get("/").text


def test_dashboard_shows_the_stop_level_and_that_the_guard_is_alive(session):
    _holding(session)
    st = get_settings(session)
    st.guard_checked_at = db._now()
    session.commit()
    html = _page()
    assert f"stop ${0.00499 * (1 - 15.0 / 100):,.6f} (-15.0% from peak $0.004990)" in html
    assert "stop guard checked" in html and "err'>stop guard" not in html


def test_dashboard_warns_when_the_guard_has_never_run_or_has_gone_quiet(session):
    from datetime import timedelta
    _holding(session)
    assert "stop guard: not running" in _page()
    st = get_settings(session)
    st.guard_checked_at = db._now() - timedelta(minutes=10)
    session.commit()
    assert "class='err'>stop guard checked" in _page()


def test_dashboard_shows_the_guard_in_cash_too_but_not_in_dry_run(session):
    st = get_settings(session)
    st.dry_run = False
    st.guard_checked_at = db._now()
    session.commit()
    assert "in USD cash" in _page() and "stop guard checked" in _page()
    st.dry_run = True
    session.commit()
    assert "stop guard" not in _page()
