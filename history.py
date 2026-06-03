"""Trade history, last (market) price per symbol, and per-user average cost.

Average cost uses a moving-average model:
  buy : avg = (avg*qty_old + price*qty) / (qty_old + qty), qty += qty
  sell: qty -= qty (average unchanged); resets to 0 when the position closes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine import Trade


@dataclass
class Position:
    quantity: int = 0
    avg_cost: int = 0  # integer smallest unit; rounded down on buys


class History:
    def __init__(self):
        self._trades: Dict[str, List[Trade]] = {}
        self._last_price: Dict[str, int] = {}
        self._positions: Dict[str, Dict[str, Position]] = {}  # user -> symbol -> Position

    # ----- recording -----------------------------------------------------
    def record(self, trade: Trade) -> None:
        symbol = trade.symbol
        self._trades.setdefault(symbol, []).append(trade)
        self._last_price[symbol] = trade.price
        if trade.buyer is not None:
            self._apply_buy(trade.buyer, symbol, trade.price, trade.quantity)
        if trade.seller is not None:
            self._apply_sell(trade.seller, symbol, trade.quantity)

    def _position(self, user: str, symbol: str) -> Position:
        by_symbol = self._positions.setdefault(user, {})
        if symbol not in by_symbol:
            by_symbol[symbol] = Position()
        return by_symbol[symbol]

    def _apply_buy(self, user: str, symbol: str, price: int, quantity: int) -> None:
        pos = self._position(user, symbol)
        total_cost = pos.avg_cost * pos.quantity + price * quantity
        pos.quantity += quantity
        pos.avg_cost = total_cost // pos.quantity if pos.quantity else 0

    def _apply_sell(self, user: str, symbol: str, quantity: int) -> None:
        pos = self._position(user, symbol)
        pos.quantity = max(0, pos.quantity - quantity)
        if pos.quantity == 0:
            pos.avg_cost = 0

    # ----- queries -------------------------------------------------------
    def trades(self, symbol: str) -> List[Trade]:
        return list(self._trades.get(symbol, []))

    def last_price(self, symbol: str) -> Optional[int]:
        return self._last_price.get(symbol)

    def average_cost(self, user: str, symbol: str) -> Optional[int]:
        pos = self._positions.get(user, {}).get(symbol)
        if pos is None or pos.quantity == 0:
            return None
        return pos.avg_cost

    def position_quantity(self, user: str, symbol: str) -> int:
        pos = self._positions.get(user, {}).get(symbol)
        return pos.quantity if pos else 0

    # ----- persistence helpers ------------------------------------------
    def set_last_price(self, symbol: str, price: int) -> None:
        self._last_price[symbol] = price

    def set_position(self, user: str, symbol: str, quantity: int, avg_cost: int) -> None:
        pos = self._position(user, symbol)
        pos.quantity = quantity
        pos.avg_cost = avg_cost

    def load_trade(self, trade: Trade) -> None:
        """Restore a trade without re-applying position maths (positions are
        persisted directly)."""
        self._trades.setdefault(trade.symbol, []).append(trade)

    def all_positions(self):
        for user, by_symbol in self._positions.items():
            for symbol, pos in by_symbol.items():
                yield user, symbol, pos
