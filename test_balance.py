import pytest

from balance import Balance, InsufficientCash, InsufficientHoldings


def test_lock_and_settle_buy_with_refund():
    b = Balance()
    b.deposit_cash("buyer", 1000)
    # lock at limit price 100 * 5 = 500
    b.lock_buy("buyer", 500)
    acct = b.account("buyer")
    assert acct.cash_available == 500 and acct.cash_locked == 500
    # fill at better price 90 -> spend 450, refund 50
    b.settle_buy("buyer", "X", 5, trade_price=90, locked_price=100)
    assert acct.cash_locked == 0
    assert acct.cash_available == 550
    assert acct.holding("X").available == 5


def test_lock_and_settle_sell():
    b = Balance()
    b.deposit_holding("seller", "X", 10)
    b.lock_sell("seller", "X", 4)
    h = b.account("seller").holding("X")
    assert h.available == 6 and h.locked == 4
    b.settle_sell("seller", "X", 4, trade_price=100)
    assert h.locked == 0
    assert b.account("seller").cash_available == 400


def test_insufficient_cash():
    b = Balance()
    b.deposit_cash("u", 100)
    with pytest.raises(InsufficientCash):
        b.lock_buy("u", 200)


def test_insufficient_holdings():
    b = Balance()
    b.deposit_holding("u", "X", 1)
    with pytest.raises(InsufficientHoldings):
        b.lock_sell("u", "X", 5)


def test_release_on_cancel():
    b = Balance()
    b.deposit_cash("u", 500)
    b.lock_buy("u", 500)
    b.release_buy("u", 500)
    assert b.account("u").cash_available == 500
    assert b.account("u").cash_locked == 0
