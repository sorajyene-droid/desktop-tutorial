import pytest

from trade_auth import (
    InvalidTradePassword,
    TradeAuth,
    TradeAuthLocked,
    TradePasswordNotSet,
)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_set_and_verify():
    ta = TradeAuth()
    ta.set_password("u", "secret")
    assert ta.verify("u", "secret") is True


def test_not_set():
    ta = TradeAuth()
    with pytest.raises(TradePasswordNotSet):
        ta.verify("u", "secret")


def test_wrong_password():
    ta = TradeAuth()
    ta.set_password("u", "secret")
    with pytest.raises(InvalidTradePassword):
        ta.verify("u", "nope")


def test_lockout_60s():
    clock = FakeClock()
    ta = TradeAuth(clock=clock)
    ta.set_password("u", "secret")
    for _ in range(4):
        with pytest.raises(InvalidTradePassword):
            ta.verify("u", "nope")
    with pytest.raises(TradeAuthLocked):
        ta.verify("u", "nope")
    with pytest.raises(TradeAuthLocked):
        ta.verify("u", "secret")
    clock.t += 61
    assert ta.verify("u", "secret") is True
