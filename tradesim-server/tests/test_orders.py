"""Order confirmation and trade bookkeeping.

Regression for the 2026-10-19 incident: Coinbase answered 404 "order with this
orderID was not found" to the confirmation lookup of a just-placed ZEC buy. The
exception escaped, the cycle rolled back, and the already-executed INJ sell and
ZEC buy were never recorded, leaving the bot blind to the ZEC it now owned."""
from types import SimpleNamespace

import pytest
import requests

from app import db, engine
from app.broker import Broker, OrderUnconfirmed, TradeResult
from app.db import Portfolio, Trade, get_portfolio
from app.predictor import Recommendation as Rec

from conftest import stat


def _http_404():
    return requests.exceptions.HTTPError(
        '404 Client Error: Not Found {"error":"NOT_FOUND","message":"order with this orderID was not found"}')


class FlakyClient:
    """get_order raises `fail_times` times, then returns a filled order."""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def get_order(self, order_id):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise _http_404()
        return {"order": {"status": "FILLED", "filled_size": "0.5", "filled_value": "133.0",
                          "total_fees": "1.2", "average_filled_price": "266.0"}}


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("app.broker.time.sleep", lambda _s: None)


def _broker(client) -> Broker:
    b = Broker(dry_run=True)
    b._client = client
    return b


def test_fill_retries_through_order_not_found(no_sleep):
    client = FlakyClient(fail_times=3)
    fill = _broker(client)._fill("order-1")
    assert fill["filled_size"] == 0.5
    assert client.calls == 4


def test_fill_raises_unconfirmed_with_order_id_when_lookup_never_succeeds(no_sleep):
    client = FlakyClient(fail_times=10_000)
    with pytest.raises(OrderUnconfirmed) as exc:
        _broker(client)._fill("order-1")
    assert exc.value.order_id == "order-1"


def test_executed_leg_survives_a_failure_in_the_next_leg(session, no_sleep):
    """Rotation INJ -> ZEC: the sell fills, the buy cannot be confirmed. The
    sell's trade row and the cash it produced must survive the rollback that
    run_once performs when the cycle fails."""
    pf = get_portfolio(session)
    pf.cash, pf.pos_base, pf.pos_product_id = 0.03, "INJ", "INJ-USD"
    pf.pos_quantity, pf.pos_cost_basis_usd, pf.pos_mark_price = 15.91, 139.87, 8.5
    session.commit()

    class FailingBuyBroker:
        fee_rate = 0.012

        def exit(self, pf, price):
            pf.cash += 134.0
            pf.pos_base = pf.pos_product_id = None
            pf.pos_quantity = pf.pos_cost_basis_usd = pf.pos_mark_price = 0.0
            return TradeResult("SELL", "INJ", price, 15.91, 134.0, -5.87, "LIVE", "o-sell", fee_usd=1.2)

        def enter(self, pf, base, product_id, price):
            raise OrderUnconfirmed("o-buy", "404")

    rec = Rec("ROTATE", "INJ", "ZEC", "test", 9.0)
    stats = {"INJ": stat("INJ", 8.5), "ZEC": stat("ZEC", 266.0)}
    with pytest.raises(OrderUnconfirmed):
        engine._execute(FailingBuyBroker(), rec, pf, stats, session,
                        SimpleNamespace(dry_run=True), "trace")
    session.rollback()  # what run_once's error handler does

    with db.SessionLocal() as fresh:
        trades = fresh.query(Trade).all()
        assert [(t.action, t.base) for t in trades] == [("SELL", "INJ")]
        saved = get_portfolio(fresh)
        assert saved.pos_base is None
        assert saved.cash == pytest.approx(134.03)


# ---- order lookups that keep failing: fills fallback, then the account itself ----

class LookupDownClient:
    """Orders are accepted but get_order always 404s (the 2026-10-20 VVV exit).
    `balances` is consumed one account listing per get_accounts call."""

    def __init__(self, balances_seq, fills=None):
        self.balances_seq = list(balances_seq)
        self.fills = fills or []
        self.placed = []

    def market_order_sell(self, client_order_id, product_id, base_size):
        self.placed.append(("SELL", product_id, base_size))
        return {"success": True, "success_response": {"order_id": "order-xyz"}}

    def market_order_buy(self, client_order_id, product_id, quote_size):
        self.placed.append(("BUY", product_id, quote_size))
        return {"success": True, "success_response": {"order_id": "order-xyz"}}

    def get_product(self, product_id):
        raise RuntimeError("no increments in tests")

    def get_order(self, order_id):
        raise _http_404()

    def get_fills(self, order_ids):
        return {"fills": self.fills}

    def get_accounts(self, limit):
        bals = self.balances_seq.pop(0) if len(self.balances_seq) > 1 else self.balances_seq[0]
        return {"accounts": [{"currency": c, "available_balance": {"value": str(v)}}
                             for c, v in bals.items()]}


def test_fill_rebuilt_from_fills_when_the_order_lookup_keeps_failing(no_sleep):
    client = LookupDownClient([{}], fills=[
        {"size": "0.06", "price": "1000", "commission": "0.54", "size_in_quote": False},
        {"size": "40", "price": "1000", "commission": "0.36", "size_in_quote": True},   # 0.04 base
    ])
    fill = _broker(client)._fill("order-xyz")
    assert fill["filled_size"] == pytest.approx(0.10)
    assert fill["filled_value"] == pytest.approx(100.0)
    assert fill["fees"] == pytest.approx(0.90)
    assert fill["avg_price"] == pytest.approx(1000.0)


def test_fill_still_unconfirmed_when_fills_are_empty_too(no_sleep):
    with pytest.raises(OrderUnconfirmed):
        _broker(LookupDownClient([{}], fills=[]))._fill("order-xyz")


def _live_broker(client) -> Broker:
    b = Broker(dry_run=True, fee_rate=0.009)   # built dry so no credentials are needed,
    b.dry_run = False                          # then pointed at the fake exchange
    b._client = client
    return b


def test_exit_is_booked_from_balances_when_the_order_cannot_be_looked_up(no_sleep):
    """VVV exit: sold on Coinbase, order unfindable. Net cash and quantity come
    from the balance change, so the trade and the cash are still recorded."""
    client = LookupDownClient([
        {"USD": 0.70, "VVV": 4.898},        # before the order
        {"USD": 123.27, "VVV": 0.0},        # after
    ])
    pf = Portfolio(cash=0.70, pos_base="VVV", pos_product_id="VVV-USD", pos_quantity=4.898,
                   pos_cost_basis_usd=126.63, pos_mark_price=25.25)
    tr = _live_broker(client).exit(pf, 25.25)
    assert client.placed[0][0] == "SELL"
    assert tr.action == "SELL" and tr.mode == "LIVE"
    assert tr.order_id == "est:order-xyz"
    assert tr.quantity == pytest.approx(4.898)
    assert tr.cash_flow == pytest.approx(122.57)
    assert tr.realized_pnl == pytest.approx(122.57 - 126.63)
    assert tr.fee_usd == pytest.approx(122.57 / 0.991 * 0.009)
    assert pf.cash == pytest.approx(123.27) and pf.pos_base is None


def test_enter_is_booked_from_balances_when_the_order_cannot_be_looked_up(no_sleep):
    client = LookupDownClient([
        {"USD": 134.5},                     # before the order
        {"USD": 0.01, "ZEC": 0.1129},       # after
    ])
    pf = Portfolio(cash=134.5)
    tr = _live_broker(client).enter(pf, "ZEC", "ZEC-USD", 1180.0)
    assert client.placed[0][0] == "BUY"
    assert tr.action == "BUY" and tr.order_id == "est:order-xyz"
    assert tr.quantity == pytest.approx(0.1129)
    assert tr.cash_flow == pytest.approx(-134.49)
    assert (pf.pos_base, pf.pos_quantity) == ("ZEC", pytest.approx(0.1129))
    assert pf.pos_cost_basis_usd == pytest.approx(134.49)
    assert pf.cash == pytest.approx(0.01)


def test_unconfirmed_order_that_the_account_does_not_show_is_not_booked(no_sleep):
    client = LookupDownClient([{"USD": 0.70, "VVV": 4.898}])     # balances never change
    pf = Portfolio(cash=0.70, pos_base="VVV", pos_product_id="VVV-USD", pos_quantity=4.898,
                   pos_cost_basis_usd=126.63, pos_mark_price=25.25)
    with pytest.raises(OrderUnconfirmed):
        _live_broker(client).exit(pf, 25.25)
    assert pf.pos_base == "VVV" and pf.cash == pytest.approx(0.70)   # books untouched
