"""Balances and credit.

Cash and per-symbol holdings, each split into available and locked.
  - buy  : lock cash (price * quantity)
  - sell : lock holdings (quantity)
  - on fill: settle (transfer), refunding any price improvement to the buyer
  - on cancel: release the lock

All amounts are integers (smallest currency unit) and share counts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


class BalanceError(Exception):
    pass


class InsufficientCash(BalanceError):
    pass


class InsufficientHoldings(BalanceError):
    pass


@dataclass
class Holding:
    available: int = 0
    locked: int = 0


@dataclass
class Account:
    cash_available: int = 0
    cash_locked: int = 0
    holdings: Dict[str, Holding] = field(default_factory=dict)

    def holding(self, symbol: str) -> Holding:
        if symbol not in self.holdings:
            self.holdings[symbol] = Holding()
        return self.holdings[symbol]


class Balance:
    def __init__(self):
        self._accounts: Dict[str, Account] = {}

    def account(self, user: str) -> Account:
        if user not in self._accounts:
            self._accounts[user] = Account()
        return self._accounts[user]

    def users(self):
        return list(self._accounts)

    # ----- deposits ------------------------------------------------------
    def deposit_cash(self, user: str, amount: int) -> None:
        if amount < 0:
            raise BalanceError("amount must be non-negative")
        self.account(user).cash_available += amount

    def deposit_holding(self, user: str, symbol: str, quantity: int) -> None:
        if quantity < 0:
            raise BalanceError("quantity must be non-negative")
        self.account(user).holding(symbol).available += quantity

    # ----- locking -------------------------------------------------------
    def lock_buy(self, user: str, amount: int) -> None:
        acct = self.account(user)
        if acct.cash_available < amount:
            raise InsufficientCash(
                f"need {amount}, have {acct.cash_available}"
            )
        acct.cash_available -= amount
        acct.cash_locked += amount

    def lock_sell(self, user: str, symbol: str, quantity: int) -> None:
        h = self.account(user).holding(symbol)
        if h.available < quantity:
            raise InsufficientHoldings(
                f"need {quantity} {symbol}, have {h.available}"
            )
        h.available -= quantity
        h.locked += quantity

    # ----- releasing (cancel) -------------------------------------------
    def release_buy(self, user: str, amount: int) -> None:
        acct = self.account(user)
        amount = min(amount, acct.cash_locked)
        acct.cash_locked -= amount
        acct.cash_available += amount

    def release_sell(self, user: str, symbol: str, quantity: int) -> None:
        h = self.account(user).holding(symbol)
        quantity = min(quantity, h.locked)
        h.locked -= quantity
        h.available += quantity

    # ----- settlement ----------------------------------------------------
    def settle_buy(self, user: str, symbol: str, quantity: int, trade_price: int, locked_price: int) -> None:
        """Buyer pays trade_price*qty out of locked cash, receives shares.
        Any difference between the locked (limit) price and the trade price is
        refunded to available cash (price improvement)."""
        acct = self.account(user)
        spend = trade_price * quantity
        locked = locked_price * quantity
        refund = locked - spend
        acct.cash_locked -= locked
        acct.cash_available += refund
        acct.holding(symbol).available += quantity

    def settle_sell(self, user: str, symbol: str, quantity: int, trade_price: int) -> None:
        """Seller delivers shares from locked holdings, receives cash."""
        acct = self.account(user)
        acct.holding(symbol).locked -= quantity
        acct.cash_available += trade_price * quantity

    # ----- views ---------------------------------------------------------
    def snapshot(self, user: str) -> dict:
        acct = self.account(user)
        return {
            "cash_available": acct.cash_available,
            "cash_locked": acct.cash_locked,
            "holdings": {
                sym: {"available": h.available, "locked": h.locked}
                for sym, h in acct.holdings.items()
            },
        }
