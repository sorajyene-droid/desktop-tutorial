from engine import OrderBook, Side


def test_resting_order_no_match():
    ob = OrderBook("X")
    order, trades = ob.add_order(Side.BUY, 100, 10)
    assert trades == []
    assert ob.best_bid() == 100
    assert order.quantity == 10


def test_full_match_at_resting_price():
    ob = OrderBook("X")
    ob.add_order(Side.SELL, 100, 5, user="seller")
    order, trades = ob.add_order(Side.BUY, 105, 5, user="buyer")
    assert len(trades) == 1
    t = trades[0]
    assert t.price == 100  # passive (resting) price
    assert t.quantity == 5
    assert t.buyer == "buyer" and t.seller == "seller"
    assert ob.best_ask() is None
    assert order.quantity == 0


def test_partial_fill_leaves_remainder():
    ob = OrderBook("X")
    ob.add_order(Side.SELL, 100, 3)
    order, trades = ob.add_order(Side.BUY, 100, 5)
    assert trades[0].quantity == 3
    assert order.quantity == 2
    assert ob.best_bid() == 100


def test_price_priority():
    ob = OrderBook("X")
    ob.add_order(Side.SELL, 102, 5)
    ob.add_order(Side.SELL, 100, 5)
    _, trades = ob.add_order(Side.BUY, 105, 5)
    assert trades[0].price == 100  # best ask first


def test_time_priority_fifo():
    ob = OrderBook("X")
    first, _ = ob.add_order(Side.SELL, 100, 5)
    second, _ = ob.add_order(Side.SELL, 100, 5)
    _, trades = ob.add_order(Side.BUY, 100, 5)
    assert trades[0].sell_order_id == first.id


def test_cancel():
    ob = OrderBook("X")
    order, _ = ob.add_order(Side.BUY, 100, 5)
    assert ob.cancel(order.id) is not None
    assert ob.best_bid() is None
    assert ob.cancel(order.id) is None


def test_depth_aggregation():
    ob = OrderBook("X")
    ob.add_order(Side.BUY, 100, 5)
    ob.add_order(Side.BUY, 100, 3)
    ob.add_order(Side.BUY, 99, 2)
    d = ob.depth()
    assert d["bids"][0] == (100, 8)
    assert d["bids"][1] == (99, 2)
