"""Multi-symbol exchange: one OrderBook per symbol."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from engine import Order, OrderBook, Side, Trade


class Exchange:
    def __init__(self, clock=None):
        self._books: Dict[str, OrderBook] = {}
        self._clock = clock

    def book(self, symbol: str) -> OrderBook:
        if symbol not in self._books:
            self._books[symbol] = OrderBook(symbol=symbol, clock=self._clock)
        return self._books[symbol]

    def symbols(self) -> List[str]:
        return sorted(self._books)

    def place_order(
        self,
        symbol: str,
        side: "Side | str",
        price: int,
        quantity: int,
        user: Optional[str] = None,
        order_id: Optional[int] = None,
    ) -> Tuple[Order, List[Trade]]:
        return self.book(symbol).add_order(side, price, quantity, user=user, order_id=order_id)

    def cancel(self, symbol: str, order_id: int) -> Optional[Order]:
        return self.book(symbol).cancel(order_id)

    def depth(self, symbol: str, levels: Optional[int] = None) -> dict:
        return self.book(symbol).depth(levels=levels)
