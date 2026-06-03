import pytest

from price_limit import OrderRejected, PriceLimit
from secured_exchange import SecuredExchange


def test_ratio_band():
    pl = PriceLimit()
    band = pl.set_limit("X", 1000, ratio=0.10)
    assert band.lower == 900 and band.upper == 1100
    pl.check("X", 900)   # ok
    pl.check("X", 1100)  # ok
    with pytest.raises(OrderRejected):
        pl.check("X", 899)
    with pytest.raises(OrderRejected):
        pl.check("X", 1101)


def test_fixed_amount_band():
    pl = PriceLimit()
    band = pl.set_limit("X", 1000, amount=50)
    assert band.lower == 950 and band.upper == 1050
    with pytest.raises(OrderRejected):
        pl.check("X", 1051)


def test_no_band_allows_anything():
    pl = PriceLimit()
    pl.check("X", 999999)  # no exception


def test_secured_exchange_rejects_out_of_band():
    ex = SecuredExchange(secret_key="test-secret")
    ex.register("a@b.com", "login", "trade")
    ex.deposit_cash("a@b.com", 1_000_000)
    token = ex.login_user("a@b.com", "login")
    ex.set_price_limit("X", reference=1000, ratio=0.10)

    # within band: ok (rests on book)
    ex.place_order(token, "trade", "X", "buy", 950, 1)

    # outside band: rejected, and no balance is locked because the check runs first
    with pytest.raises(OrderRejected):
        ex.place_order(token, "trade", "X", "buy", 1200, 1)
