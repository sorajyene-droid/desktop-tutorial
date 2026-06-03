import pytest
from fastapi.testclient import TestClient

from api import create_app
from secured_exchange import SecuredExchange


@pytest.fixture
def client(tmp_path):
    ex = SecuredExchange(secret_key="test-secret", db_path=str(tmp_path / "api.db"))
    # seed two funded users and a symbol description
    ex.register("buyer@x.com", "loginpw", "tradepw")
    ex.register("seller@x.com", "loginpw", "tradepw")
    ex.deposit_cash("buyer@x.com", 1_000_000)
    ex.deposit_holding("seller@x.com", "X", 100)
    ex.set_symbol_info("X", "Example Corp", "A test symbol")
    app = create_app(ex)
    return TestClient(app)


def _login(client, email):
    r = client.post("/login", json={"email": email, "login_password": "loginpw"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_register_login_order_flow(client):
    buyer = _login(client, "buyer@x.com")
    seller = _login(client, "seller@x.com")

    # seller posts a resting ask
    r = client.post(
        "/order",
        headers={"Authorization": f"Bearer {seller}"},
        json={"trade_password": "tradepw", "symbol": "X", "side": "sell", "price": 100, "quantity": 10},
    )
    assert r.status_code == 200, r.text
    assert r.json()["trades"] == []

    # buyer crosses -> trade at 100
    r = client.post(
        "/order",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"trade_password": "tradepw", "symbol": "X", "side": "buy", "price": 105, "quantity": 10},
    )
    assert r.status_code == 200, r.text
    trades = r.json()["trades"]
    assert len(trades) == 1
    assert trades[0]["price"] == 100 and trades[0]["quantity"] == 10

    # depth shows last price and an empty book
    d = client.get("/depth/X").json()
    assert d["last_price"] == 100
    assert d["bids"] == [] and d["asks"] == []

    # portfolio of buyer reflects holdings + refund (limit 105, filled 100)
    p = client.get("/portfolio", headers={"Authorization": f"Bearer {buyer}"}).json()
    pos = {x["symbol"]: x for x in p["positions"]}
    assert pos["X"]["quantity"] == 10
    assert pos["X"]["avg_cost"] == 100
    # cash: 1,000,000 - 100*10 spent = 999,000 total
    assert p["cash_total"] == 999_000

    # history and chart
    h = client.get("/history/X").json()
    assert len(h["trades"]) == 1
    chart = client.get("/chart/X", params={"timeframe": "1d"}).json()
    assert len(chart["candles"]) == 1

    # symbol info
    info = client.get("/symbol/X").json()
    assert info["name"] == "Example Corp"


def test_order_requires_auth(client):
    r = client.post(
        "/order",
        json={"trade_password": "tradepw", "symbol": "X", "side": "buy", "price": 100, "quantity": 1},
    )
    assert r.status_code == 401


def test_wrong_trade_password(client):
    buyer = _login(client, "buyer@x.com")
    r = client.post(
        "/order",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"trade_password": "WRONG", "symbol": "X", "side": "buy", "price": 100, "quantity": 1},
    )
    assert r.status_code == 403


def test_price_limit_endpoint_rejects(client):
    buyer = _login(client, "buyer@x.com")
    client.post(
        "/price_limit",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"symbol": "X", "reference": 100, "ratio": 0.10},
    )
    r = client.post(
        "/order",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"trade_password": "tradepw", "symbol": "X", "side": "buy", "price": 200, "quantity": 1},
    )
    assert r.status_code == 422


def test_websocket_snapshot_and_update(client):
    seller = _login(client, "seller@x.com")
    buyer = _login(client, "buyer@x.com")

    with client.websocket_connect("/ws/X") as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["symbol"] == "X"

        # a resting sell should push an update
        client.post(
            "/order",
            headers={"Authorization": f"Bearer {seller}"},
            json={"trade_password": "tradepw", "symbol": "X", "side": "sell", "price": 100, "quantity": 5},
        )
        msg = ws.receive_json()
        assert msg["type"] == "update"
        assert msg["depth"]["asks"] == [[100, 5]]

        # a crossing buy should push an update containing the trade
        client.post(
            "/order",
            headers={"Authorization": f"Bearer {buyer}"},
            json={"trade_password": "tradepw", "symbol": "X", "side": "buy", "price": 100, "quantity": 5},
        )
        msg = ws.receive_json()
        assert msg["type"] == "update"
        assert len(msg["trades"]) == 1
        assert msg["trades"][0]["price"] == 100
