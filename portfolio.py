"""Portfolio valuation and unrealised profit/loss.

Cash (available + locked) plus each holding valued at market price.
Market price = last trade price -> else average cost -> else 0.
Unrealised P&L = market value - cost basis (quantity * average cost).
"""
from __future__ import annotations

from typing import Dict

from balance import Balance
from history import History


class Portfolio:
    def __init__(self, balance: Balance, history: History):
        self._balance = balance
        self._history = history

    def market_price(self, symbol: str, avg_cost: int = 0) -> int:
        last = self._history.last_price(symbol)
        if last is not None:
            return last
        if avg_cost:
            return avg_cost
        return 0

    def valuation(self, user: str) -> dict:
        acct = self._balance.account(user)
        cash = acct.cash_available + acct.cash_locked

        positions = []
        holdings_value = 0
        total_cost_basis = 0
        for symbol, h in acct.holdings.items():
            quantity = h.available + h.locked
            if quantity == 0:
                continue
            avg_cost = self._history.average_cost(user, symbol) or 0
            price = self.market_price(symbol, avg_cost)
            value = price * quantity
            cost_basis = avg_cost * quantity
            unrealized = value - cost_basis
            holdings_value += value
            total_cost_basis += cost_basis
            positions.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "available": h.available,
                    "locked": h.locked,
                    "avg_cost": avg_cost,
                    "market_price": price,
                    "market_value": value,
                    "cost_basis": cost_basis,
                    "unrealized_pnl": unrealized,
                }
            )

        return {
            "cash_available": acct.cash_available,
            "cash_locked": acct.cash_locked,
            "cash_total": cash,
            "holdings_value": holdings_value,
            "total_value": cash + holdings_value,
            "total_cost_basis": total_cost_basis,
            "unrealized_pnl": holdings_value - total_cost_basis,
            "positions": positions,
        }
