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
from app.db import Trade, get_portfolio
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
