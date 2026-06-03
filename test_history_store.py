import os

import pytest

from balance import Balance
from engine import Trade
from history import History
from store import Store


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


def make_trade(symbol, price, qty, buyer, seller, ts=0.0):
    return Trade(
        buy_order_id=1, sell_order_id=2, price=price, quantity=qty,
        timestamp=ts, buyer=buyer, seller=seller, symbol=symbol,
    )


def test_last_price_and_history():
    h = History()
    h.record(make_trade("X", 100, 5, "a", "b"))
    h.record(make_trade("X", 110, 3, "a", "b"))
    assert h.last_price("X") == 110
    assert len(h.trades("X")) == 2


def test_average_cost_moving():
    h = History()
    h.record(make_trade("X", 100, 10, "a", "b"))
    h.record(make_trade("X", 200, 10, "a", "b"))
    # (100*10 + 200*10)/20 = 150
    assert h.average_cost("a", "X") == 150
    assert h.position_quantity("a", "X") == 20
    # seller position decreased
    assert h.position_quantity("b", "X") == 0


def test_average_cost_resets_on_close():
    h = History()
    h.record(make_trade("X", 100, 5, "a", "b"))
    # 'a' buys 5; now 'a' sells all 5 (a becomes seller)
    h.record(make_trade("X", 120, 5, "c", "a"))
    assert h.average_cost("a", "X") is None


def test_store_roundtrip(tmp_db):
    b = Balance()
    b.deposit_cash("u", 1000)
    b.deposit_holding("u", "X", 7)
    b.account("u").cash_locked = 200

    h = History()
    h.record(make_trade("X", 100, 5, "u", "v", ts=1.0))
    h.set_position("u", "X", 5, 100)

    store = Store(tmp_db)
    store.append_trade(make_trade("X", 100, 5, "u", "v", ts=1.0))
    store.save_last_price("X", 100)
    store.save_all(b, h)
    store.close()

    # reload into fresh objects
    b2 = Balance()
    h2 = History()
    store2 = Store(tmp_db)
    store2.load_all(b2, h2)

    assert b2.account("u").cash_available == 1000
    assert b2.account("u").cash_locked == 200
    assert b2.account("u").holding("X").available == 7
    assert h2.last_price("X") == 100
    assert h2.average_cost("u", "X") == 100
    assert len(h2.trades("X")) == 1
    store2.close()
