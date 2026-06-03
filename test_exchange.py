from exchange import Exchange
from engine import Side


def test_separate_books_per_symbol():
    ex = Exchange()
    ex.place_order("AAA", Side.BUY, 100, 5)
    ex.place_order("BBB", Side.SELL, 200, 3)
    assert ex.depth("AAA")["bids"] == [(100, 5)]
    assert ex.depth("BBB")["asks"] == [(200, 3)]
    assert ex.symbols() == ["AAA", "BBB"]


def test_match_within_symbol_only():
    ex = Exchange()
    ex.place_order("AAA", Side.SELL, 100, 5)
    _, trades = ex.place_order("BBB", Side.BUY, 100, 5)
    assert trades == []  # different symbol, no cross
    _, trades = ex.place_order("AAA", Side.BUY, 100, 5)
    assert len(trades) == 1
