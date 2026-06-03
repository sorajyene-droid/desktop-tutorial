import pytest

from chart import SymbolInfoStore, candles, candles_with_ma, sma
from engine import Trade


def t(price, qty, ts):
    return Trade(buy_order_id=1, sell_order_id=2, price=price, quantity=qty,
                 timestamp=ts, symbol="X")


def test_candles_bucketing_1m():
    trades = [t(100, 1, 0), t(110, 1, 10), t(90, 1, 30), t(105, 2, 70)]
    cs = candles(trades, "1m")
    assert len(cs) == 2
    first = cs[0]
    assert first.open == 100
    assert first.high == 110
    assert first.low == 90
    assert first.close == 90
    assert first.volume == 3
    assert cs[1].open == 105 and cs[1].volume == 2


def test_sma():
    vals = [10, 20, 30, 40]
    out = sma(vals, 2)
    assert out[0] is None
    assert out[1] == 15
    assert out[2] == 25
    assert out[3] == 35


def test_candles_with_ma():
    trades = [t(100, 1, i * 60) for i in range(5)]
    result = candles_with_ma(trades, "1m", periods=(2,))
    assert result["timeframe"] == "1m"
    assert len(result["candles"]) == 5
    assert "sma2" in result["ma"]


def test_unknown_timeframe():
    with pytest.raises(ValueError):
        candles([], "13s")


def test_symbol_info_store():
    s = SymbolInfoStore(":memory:")
    assert s.get_info("X") is None
    s.set_info("X", "Example Corp", "A test symbol")
    info = s.get_info("X")
    assert info["name"] == "Example Corp"
    assert info["description"] == "A test symbol"
    s.set_info("X", "Renamed", "updated")
    assert s.get_info("X")["name"] == "Renamed"
    s.close()
