"""SecuredExchange: the full system tied together.

Order placement flow:
  login check -> trade-password check -> price-band check -> balance lock
  -> match -> settle -> record history -> persist.

The order book itself is not persisted; balances, positions, last prices and
trade history are.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from balance import Balance
from chart import SymbolInfoStore, candles_with_ma
from engine import Order, Side, Trade
from exchange import Exchange
from history import History
from login_auth import LoginAuth
from portfolio import Portfolio
from price_limit import OrderRejected, PriceLimit
from store import Store
from trade_auth import TradeAuth


@dataclass
class _Meta:
    user: str
    symbol: str
    side: Side
    limit_price: int
    remaining: int


@dataclass
class OrderResult:
    order: Order
    trades: List[Trade]

    def to_dict(self) -> dict:
        return {
            "order": self.order.to_dict(),
            "trades": [t.to_dict() for t in self.trades],
        }


class SecuredExchange:
    def __init__(
        self,
        secret_key: str,
        db_path: Optional[str] = None,
        token_ttl: int = 3600,
        clock: Optional[Callable[[], float]] = None,
    ):
        # default to wall-clock so trade timestamps drive realistic charts
        self._clock = clock or time.time
        self._login = LoginAuth(secret_key, token_ttl=token_ttl, clock=clock)
        self._trade_auth = TradeAuth(clock=clock)
        self._exchange = Exchange(clock=clock)
        self._balance = Balance()
        self._history = History()
        self._portfolio = Portfolio(self._balance, self._history)
        self._price_limit = PriceLimit()
        self._meta: Dict[int, _Meta] = {}
        self._symbol_info = SymbolInfoStore(db_path or ":memory:")

        self._store: Optional[Store] = None
        if db_path:
            self._store = Store(db_path)
            self._store.load_all(self._balance, self._history)

    # expose for the API layer
    @property
    def login(self) -> LoginAuth:
        return self._login

    # ----- account setup -------------------------------------------------
    def register(self, email: str, login_password: str, trade_password: str) -> str:
        email = self._login.register(email, login_password)
        self._trade_auth.set_password(email, trade_password)
        self._persist()
        return email

    def login_user(self, email: str, login_password: str) -> str:
        return self._login.login(email, login_password)

    def deposit_cash(self, user: str, amount: int) -> None:
        self._balance.deposit_cash(user, amount)
        self._persist()

    def deposit_holding(self, user: str, symbol: str, quantity: int) -> None:
        self._balance.deposit_holding(user, symbol, quantity)
        self._persist()

    def set_price_limit(self, symbol: str, reference: int, ratio: float = 0.10, amount: Optional[int] = None):
        return self._price_limit.set_limit(symbol, reference, ratio=ratio, amount=amount)

    # ----- order placement ----------------------------------------------
    def place_order(
        self,
        token: str,
        trade_password: str,
        symbol: str,
        side: "Side | str",
        price: int,
        quantity: int,
    ) -> OrderResult:
        # 1. login check
        user = self._login.verify_token(token)
        # 2. trade-password check
        self._trade_auth.verify(user, trade_password)
        # 3. price-band check
        side = Side.parse(side)
        self._price_limit.check(symbol, price)
        if price <= 0 or quantity <= 0:
            raise OrderRejected("price and quantity must be positive")

        # 4. balance lock
        if side is Side.BUY:
            self._balance.lock_buy(user, price * quantity)
        else:
            self._balance.lock_sell(user, symbol, quantity)

        # 5. match
        order, trades = self._exchange.place_order(symbol, side, price, quantity, user=user)
        self._meta[order.id] = _Meta(user, symbol, side, price, order.quantity)

        # 6. settle each trade
        for t in trades:
            self._settle(t)

        # 7. record history + 8. persist
        for t in trades:
            self._history.record(t)
            if self._store:
                self._store.append_trade(t)
                self._store.save_last_price(t.symbol, t.price)
        self._persist()

        return OrderResult(order=order, trades=trades)

    def _settle(self, t: Trade) -> None:
        buy_meta = self._meta.get(t.buy_order_id)
        sell_meta = self._meta.get(t.sell_order_id)
        # buyer side
        if t.buyer is not None:
            locked_price = buy_meta.limit_price if buy_meta else t.price
            self._balance.settle_buy(t.buyer, t.symbol, t.quantity, t.price, locked_price)
        if t.seller is not None:
            self._balance.settle_sell(t.seller, t.symbol, t.quantity, t.price)
        # track remaining; drop fully-filled metas
        for meta_id in (t.buy_order_id, t.sell_order_id):
            meta = self._meta.get(meta_id)
            if meta is not None:
                meta.remaining -= t.quantity
                if meta.remaining <= 0:
                    self._meta.pop(meta_id, None)

    def cancel(self, token: str, symbol: str, order_id: int) -> Optional[Order]:
        user = self._login.verify_token(token)
        meta = self._meta.get(order_id)
        if meta is None or meta.user != user:
            return None
        order = self._exchange.cancel(symbol, order_id)
        if order is None:
            return None
        # release the remaining lock
        if meta.side is Side.BUY:
            self._balance.release_buy(user, meta.limit_price * order.quantity)
        else:
            self._balance.release_sell(user, symbol, order.quantity)
        self._meta.pop(order_id, None)
        self._persist()
        return order

    # ----- queries -------------------------------------------------------
    def user_from_token(self, token: str) -> str:
        return self._login.verify_token(token)

    def depth(self, symbol: str, levels: Optional[int] = None) -> dict:
        d = self._exchange.depth(symbol, levels=levels)
        d["last_price"] = self._history.last_price(symbol)
        return d

    def chart(self, symbol: str, timeframe: str = "1d", periods=(5, 25)) -> dict:
        return candles_with_ma(self._history.trades(symbol), timeframe, periods=periods)

    def portfolio(self, user: str) -> dict:
        return self._portfolio.valuation(user)

    def trade_history(self, symbol: str) -> List[dict]:
        return [t.to_dict() for t in self._history.trades(symbol)]

    def last_price(self, symbol: str) -> Optional[int]:
        return self._history.last_price(symbol)

    def symbol_info(self, symbol: str) -> Optional[dict]:
        return self._symbol_info.get_info(symbol)

    def set_symbol_info(self, symbol: str, name: str = "", description: str = "") -> None:
        self._symbol_info.set_info(symbol, name, description)

    # ----- internals -----------------------------------------------------
    def _persist(self) -> None:
        if self._store:
            self._store.save_all(self._balance, self._history)
