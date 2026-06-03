"""Charting: candlesticks from trade history, simple moving averages, and a
SQLite-backed symbol description master.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional

from engine import Trade

# timeframe -> seconds
TIMEFRAMES: Dict[str, int] = {
    "1m": 60,
    "5m": 5 * 60,
    "1h": 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
    "1mo": 30 * 24 * 60 * 60,
}


@dataclass
class Candle:
    time: int        # bucket start (epoch seconds)
    open: int
    high: int
    low: int
    close: int
    volume: int

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


def candles(trades: List[Trade], timeframe: str = "1d") -> List[Candle]:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unknown timeframe {timeframe!r}")
    span = TIMEFRAMES[timeframe]
    buckets: Dict[int, Candle] = {}
    for t in sorted(trades, key=lambda x: x.timestamp):
        bucket = int(t.timestamp // span) * span
        c = buckets.get(bucket)
        if c is None:
            buckets[bucket] = Candle(
                time=bucket, open=t.price, high=t.price,
                low=t.price, close=t.price, volume=t.quantity,
            )
        else:
            c.high = max(c.high, t.price)
            c.low = min(c.low, t.price)
            c.close = t.price
            c.volume += t.quantity
    return [buckets[k] for k in sorted(buckets)]


def sma(values: List[int], period: int) -> List[Optional[float]]:
    """Simple moving average. Entries before `period` samples are None."""
    out: List[Optional[float]] = []
    running = 0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out.append(running / period)
        else:
            out.append(None)
    return out


def candles_with_ma(trades: List[Trade], timeframe: str = "1d", periods=(5, 25)) -> dict:
    cs = candles(trades, timeframe)
    closes = [c.close for c in cs]
    mas = {f"sma{p}": sma(closes, p) for p in periods}
    return {
        "timeframe": timeframe,
        "candles": [c.to_dict() for c in cs],
        "ma": mas,
    }


class SymbolInfoStore:
    """SQLite master of symbol descriptions."""

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS symbol_info (
                   symbol      TEXT PRIMARY KEY,
                   name        TEXT,
                   description TEXT
               )"""
        )
        self._conn.commit()

    def set_info(self, symbol: str, name: str = "", description: str = "") -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO symbol_info (symbol, name, description) VALUES (?, ?, ?)",
            (symbol, name, description),
        )
        self._conn.commit()

    def get_info(self, symbol: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT symbol, name, description FROM symbol_info WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        if row is None:
            return None
        return {"symbol": row[0], "name": row[1], "description": row[2]}

    def close(self) -> None:
        self._conn.close()
