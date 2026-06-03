"""Matching engine for a single symbol.

Continuous (double) auction with price priority then time priority.
All prices and quantities are integers (smallest unit). No floats are used
for money or quantity.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from itertools import count
from typing import Deque, Dict, List, Optional, Tuple


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"

    @classmethod
    def parse(cls, value: "Side | str") -> "Side":
        if isinstance(value, Side):
            return value
        return cls(str(value).lower())


@dataclass
class Order:
    id: int
    side: Side
    price: int
    quantity: int          # remaining quantity on the book
    user: Optional[str] = None
    sequence: int = 0       # monotonic, used for time priority
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "side": self.side.value,
            "price": self.price,
            "quantity": self.quantity,
            "user": self.user,
        }


@dataclass
class Trade:
    buy_order_id: int
    sell_order_id: int
    price: int
    quantity: int
    timestamp: float = 0.0
    buyer: Optional[str] = None
    seller: Optional[str] = None
    symbol: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "buy_order_id": self.buy_order_id,
            "sell_order_id": self.sell_order_id,
            "price": self.price,
            "quantity": self.quantity,
            "timestamp": self.timestamp,
            "buyer": self.buyer,
            "seller": self.seller,
            "symbol": self.symbol,
        }


class OrderBook:
    """A single-symbol limit order book running a continuous auction."""

    def __init__(self, symbol: str = "", clock=None):
        self.symbol = symbol
        # price -> FIFO queue of resting orders
        self._bids: Dict[int, Deque[Order]] = {}
        self._asks: Dict[int, Deque[Order]] = {}
        self._orders: Dict[int, Order] = {}
        self._id_gen = count(1)
        self._seq_gen = count(1)
        self._clock = clock or (lambda: 0.0)

    # ----- introspection -------------------------------------------------
    def best_bid(self) -> Optional[int]:
        return max(self._bids) if self._bids else None

    def best_ask(self) -> Optional[int]:
        return min(self._asks) if self._asks else None

    def get_order(self, order_id: int) -> Optional[Order]:
        return self._orders.get(order_id)

    def depth(self, levels: Optional[int] = None) -> dict:
        """Aggregated book. Bids descending, asks ascending."""
        bids = [
            (price, sum(o.quantity for o in self._bids[price]))
            for price in sorted(self._bids, reverse=True)
        ]
        asks = [
            (price, sum(o.quantity for o in self._asks[price]))
            for price in sorted(self._asks)
        ]
        if levels is not None:
            bids = bids[:levels]
            asks = asks[:levels]
        return {"symbol": self.symbol, "bids": bids, "asks": asks}

    # ----- mutation ------------------------------------------------------
    def add_order(
        self,
        side: "Side | str",
        price: int,
        quantity: int,
        user: Optional[str] = None,
        order_id: Optional[int] = None,
    ) -> Tuple[Order, List[Trade]]:
        side = Side.parse(side)
        if price <= 0:
            raise ValueError("price must be positive")
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        oid = order_id if order_id is not None else next(self._id_gen)
        order = Order(
            id=oid,
            side=side,
            price=price,
            quantity=quantity,
            user=user,
            sequence=next(self._seq_gen),
            timestamp=self._clock(),
        )

        if side is Side.BUY:
            trades = self._match(order, self._asks, is_buy=True)
        else:
            trades = self._match(order, self._bids, is_buy=False)

        # whatever is left rests on the book
        if order.quantity > 0:
            book = self._bids if side is Side.BUY else self._asks
            book.setdefault(order.price, deque()).append(order)
            self._orders[order.id] = order
        return order, trades

    def cancel(self, order_id: int) -> Optional[Order]:
        order = self._orders.get(order_id)
        if order is None:
            return None
        book = self._bids if order.side is Side.BUY else self._asks
        queue = book.get(order.price)
        if queue is not None:
            try:
                queue.remove(order)
            except ValueError:
                pass
            if not queue:
                del book[order.price]
        del self._orders[order_id]
        return order

    # ----- internals -----------------------------------------------------
    def _match(self, incoming: Order, opposite: Dict[int, Deque[Order]], is_buy: bool) -> List[Trade]:
        trades: List[Trade] = []
        while incoming.quantity > 0 and opposite:
            best = min(opposite) if is_buy else max(opposite)
            # price condition: buyer pays up to its price, seller accepts down to its price
            if is_buy and best > incoming.price:
                break
            if not is_buy and best < incoming.price:
                break

            queue = opposite[best]
            while queue and incoming.quantity > 0:
                resting = queue[0]
                qty = min(incoming.quantity, resting.quantity)
                # trade executes at the resting (passive) order's price
                trade_price = resting.price
                if is_buy:
                    buy_id, sell_id = incoming.id, resting.id
                    buyer, seller = incoming.user, resting.user
                else:
                    buy_id, sell_id = resting.id, incoming.id
                    buyer, seller = resting.user, incoming.user
                trades.append(
                    Trade(
                        buy_order_id=buy_id,
                        sell_order_id=sell_id,
                        price=trade_price,
                        quantity=qty,
                        timestamp=self._clock(),
                        buyer=buyer,
                        seller=seller,
                        symbol=self.symbol,
                    )
                )
                incoming.quantity -= qty
                resting.quantity -= qty
                if resting.quantity == 0:
                    queue.popleft()
                    self._orders.pop(resting.id, None)
            if not queue:
                del opposite[best]
        return trades
