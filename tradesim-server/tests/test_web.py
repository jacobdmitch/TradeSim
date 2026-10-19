"""Dashboard routes: the holding picker, Go LIVE with a pick, and Reconcile."""
import pytest
from fastapi.testclient import TestClient

from app import config, db, web
from app.db import get_settings

from conftest import stat

HOLDINGS = [("ZEC", 0.5, 133.0), ("INJ", 2.0, 17.0)]
USD = 0.01


@pytest.fixture
def client(session, monkeypatch):
    monkeypatch.setattr(web, "run_once", lambda force=False: None)
    monkeypatch.setattr(web, "_live_holdings", lambda: (HOLDINGS, USD))
    monkeypatch.setattr(config, "DASHBOARD_TOKEN", "")
    return TestClient(web.app, follow_redirects=False)


def _settings():
    with db.SessionLocal() as s:
        st = get_settings(s)
        return st.dry_run, st.seeded, st.adopt_base, st.starting_balance, st.history_since


def test_live_holdings_lists_manageable_coins_largest_first(monkeypatch):
    class FakeLiveBroker:
        def __init__(self, dry_run):
            assert dry_run is False

        def balances(self):
            return {"USD": 3.0, "INJ": 2.0, "ZEC": 0.5, "USDC": 50.0, "DUST": 0.00001,
                    "NOMARKET": 5.0, "bad-code": 1.0}

    monkeypatch.setattr(web, "Broker", FakeLiveBroker)
    monkeypatch.setattr(web.market, "fetch_usd_products", lambda: [])
    monkeypatch.setattr(web.market, "fetch_stats",
                        lambda products: [stat("ZEC", 266.0), stat("INJ", 8.5), stat("DUST", 1.0),
                                          stat("bad-code", 5.0)])
    coins, usd = web._live_holdings()
    assert [c[0] for c in coins] == ["ZEC", "INJ"]
    assert coins[0][2] == pytest.approx(133.0)
    assert usd == 3.0


def test_picker_lists_coins_and_usd(client):
    html = client.post("/pick", data={"kind": "golive"}).text
    assert 'name="asset" value="ZEC"' in html and 'name="asset" value="INJ"' in html
    assert 'name="asset" value="USD"' in html
    assert "$133.00" in html
    assert 'action="/toggle/dry-run"' in html and 'name="confirm"' in html


def test_reconcile_picker_posts_to_reconcile_without_live_confirmation(client):
    with db.SessionLocal() as s:
        get_settings(s).dry_run = False
        s.commit()
    html = client.post("/pick", data={"kind": "reconcile"}).text
    assert 'action="/reconcile"' in html and 'name="confirm"' not in html


def test_picker_shows_the_error_when_balances_cannot_be_read(client, monkeypatch):
    def boom():
        raise RuntimeError("401 Unauthorized")
    monkeypatch.setattr(web, "_live_holdings", boom)
    html = client.post("/pick", data={"kind": "golive"}).text
    assert "Could not read your Coinbase balances" in html
    assert 'name="asset"' not in html


def test_picker_requires_the_token_when_one_is_configured(client, monkeypatch):
    monkeypatch.setattr(config, "DASHBOARD_TOKEN", "secret")
    r = client.post("/pick", data={"kind": "golive"})
    assert r.status_code == 303 and r.headers["location"] == "/?err=auth"
    assert client.post("/pick", data={"kind": "golive", "token": "secret"}).status_code == 200


def test_go_live_with_a_pick_records_it(client):
    r = client.post("/toggle/dry-run", data={"confirm": "LIVE", "asset": "zec"})
    assert r.status_code == 303 and r.headers["location"] == "/"
    dry, seeded, adopt, *_ = _settings()
    assert (dry, seeded, adopt) == (False, False, "ZEC")


def test_go_live_requires_a_pick(client):
    r = client.post("/toggle/dry-run", data={"confirm": "LIVE"})
    assert r.headers["location"] == "/?err=asset"
    assert _settings()[0] is True  # still dry-run


def test_go_live_rejects_a_malformed_pick(client):
    r = client.post("/toggle/dry-run", data={"confirm": "LIVE", "asset": "ZEC; DROP TABLE"})
    assert r.headers["location"] == "/?err=asset"
    assert _settings()[0] is True


def test_go_live_still_requires_typing_live(client):
    r = client.post("/toggle/dry-run", data={"confirm": "nope", "asset": "ZEC"})
    assert r.headers["location"] == "/?err=confirm"
    assert _settings()[0] is True


def test_reconcile_records_the_pick_without_rebaselining(client):
    with db.SessionLocal() as s:
        st = get_settings(s)
        st.dry_run, st.seeded, st.starting_balance = False, True, 161.05
        s.commit()
    r = client.post("/reconcile", data={"asset": "ZEC"})
    assert r.status_code == 303 and r.headers["location"] == "/"
    dry, seeded, adopt, baseline, since = _settings()
    assert (dry, seeded, adopt, baseline, since) == (False, True, "ZEC", 161.05, None)


def test_reconcile_is_live_only(client):
    r = client.post("/reconcile", data={"asset": "ZEC"})
    assert r.headers["location"] == "/?err=reconcile"
    assert _settings()[2] is None


def test_dashboard_offers_the_right_buttons_per_mode(client):
    assert 'name="kind" value="golive"' in client.get("/").text
    with db.SessionLocal() as s:
        get_settings(s).dry_run = False
        s.commit()
    html = client.get("/").text
    assert 'name="kind" value="reconcile"' in html and "Back to DRY-RUN" in html


def test_dashboard_flags_untracked_holdings_from_the_last_scan(client):
    with db.SessionLocal() as s:
        s.add(db.ScanLog(candidates=0, note="mode=LIVE untracked:ZEC($133),INJ($17)"))
        s.commit()
    html = client.get("/").text
    assert "Untracked on Coinbase: ZEC($133),INJ($17)" in html
