"""SQLite persistence for balances, holdings, trade history, average cost, and
last prices. The order book (resting orders) is intentionally NOT persisted.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, List

from balance import Balance
from engine import Trade
from history import History


class Store:
    def __init__(self, db_path: str):
        # check_same_thread=False: FastAPI serves sync and async endpoints from
        # different threads but accesses share one exchange/connection.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        c = self._conn
        c.execute(
            """CREATE TABLE IF NOT EXISTS accounts (
                   user TEXT PRIMARY KEY,
                   cash_available INTEGER NOT NULL,
                   cash_locked INTEGER NOT NULL
               )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS holdings (
                   user TEXT NOT NULL,
                   symbol TEXT NOT NULL,
                   available INTEGER NOT NULL,
                   locked INTEGER NOT NULL,
                   PRIMARY KEY (user, symbol)
               )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS positions (
                   user TEXT NOT NULL,
                   symbol TEXT NOT NULL,
                   quantity INTEGER NOT NULL,
                   avg_cost INTEGER NOT NULL,
                   PRIMARY KEY (user, symbol)
               )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS last_prices (
                   symbol TEXT PRIMARY KEY,
                   price INTEGER NOT NULL
               )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS trades (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   symbol TEXT NOT NULL,
                   buy_order_id INTEGER,
                   sell_order_id INTEGER,
                   price INTEGER NOT NULL,
                   quantity INTEGER NOT NULL,
                   timestamp REAL NOT NULL,
                   buyer TEXT,
                   seller TEXT
               )"""
        )
        c.commit()

    # ----- saving --------------------------------------------------------
    def save_balance(self, balance: Balance) -> None:
        c = self._conn
        for user in balance.users():
            acct = balance.account(user)
            c.execute(
                "INSERT OR REPLACE INTO accounts (user, cash_available, cash_locked) VALUES (?, ?, ?)",
                (user, acct.cash_available, acct.cash_locked),
            )
            for symbol, h in acct.holdings.items():
                c.execute(
                    "INSERT OR REPLACE INTO holdings (user, symbol, available, locked) VALUES (?, ?, ?, ?)",
                    (user, symbol, h.available, h.locked),
                )
        c.commit()

    def save_history(self, history: History) -> None:
        c = self._conn
        for user, symbol, pos in history.all_positions():
            c.execute(
                "INSERT OR REPLACE INTO positions (user, symbol, quantity, avg_cost) VALUES (?, ?, ?, ?)",
                (user, symbol, pos.quantity, pos.avg_cost),
            )
        c.commit()

    def save_last_price(self, symbol: str, price: int) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO last_prices (symbol, price) VALUES (?, ?)",
            (symbol, price),
        )
        self._conn.commit()

    def append_trade(self, trade: Trade) -> None:
        self._conn.execute(
            """INSERT INTO trades
               (symbol, buy_order_id, sell_order_id, price, quantity, timestamp, buyer, seller)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.symbol, trade.buy_order_id, trade.sell_order_id,
                trade.price, trade.quantity, trade.timestamp, trade.buyer, trade.seller,
            ),
        )
        self._conn.commit()

    def save_all(self, balance: Balance, history: History) -> None:
        self.save_balance(balance)
        self.save_history(history)

    # ----- loading -------------------------------------------------------
    def load_balance(self, balance: Balance) -> None:
        for user, cash_available, cash_locked in self._conn.execute(
            "SELECT user, cash_available, cash_locked FROM accounts"
        ):
            acct = balance.account(user)
            acct.cash_available = cash_available
            acct.cash_locked = cash_locked
        for user, symbol, available, locked in self._conn.execute(
            "SELECT user, symbol, available, locked FROM holdings"
        ):
            h = balance.account(user).holding(symbol)
            h.available = available
            h.locked = locked

    def load_history(self, history: History) -> None:
        for symbol, price in self._conn.execute("SELECT symbol, price FROM last_prices"):
            history.set_last_price(symbol, price)
        for user, symbol, quantity, avg_cost in self._conn.execute(
            "SELECT user, symbol, quantity, avg_cost FROM positions"
        ):
            history.set_position(user, symbol, quantity, avg_cost)
        for row in self._conn.execute(
            """SELECT symbol, buy_order_id, sell_order_id, price, quantity, timestamp, buyer, seller
               FROM trades ORDER BY id"""
        ):
            history.load_trade(
                Trade(
                    symbol=row[0], buy_order_id=row[1], sell_order_id=row[2],
                    price=row[3], quantity=row[4], timestamp=row[5],
                    buyer=row[6], seller=row[7],
                )
            )

    def load_all(self, balance: Balance, history: History) -> None:
        self.load_balance(balance)
        self.load_history(history)

    def close(self) -> None:
        self._conn.close()
