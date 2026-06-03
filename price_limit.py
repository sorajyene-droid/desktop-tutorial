"""Price band limits (limit-up / limit-down).

A band is defined per symbol from a reference price, either by ratio
(default 10%) or by a fixed absolute amount. Orders priced outside the
[lower, upper] band are rejected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


class OrderRejected(Exception):
    pass


@dataclass
class Band:
    reference: int
    lower: int
    upper: int


class PriceLimit:
    def __init__(self):
        self._bands: Dict[str, Band] = {}

    def set_limit(
        self,
        symbol: str,
        reference: int,
        ratio: Optional[float] = 0.10,
        amount: Optional[int] = None,
    ) -> Band:
        """Set the band for a symbol.

        If `amount` is given it takes precedence (fixed absolute width);
        otherwise `ratio` (fraction of the reference) is used.
        """
        if reference <= 0:
            raise ValueError("reference must be positive")
        if amount is not None:
            width = int(amount)
        else:
            if ratio is None:
                raise ValueError("either ratio or amount is required")
            width = int(reference * ratio)
        lower = max(1, reference - width)
        upper = reference + width
        band = Band(reference=reference, lower=lower, upper=upper)
        self._bands[symbol] = band
        return band

    def clear(self, symbol: str) -> None:
        self._bands.pop(symbol, None)

    def band(self, symbol: str) -> Optional[Band]:
        return self._bands.get(symbol)

    def check(self, symbol: str, price: int) -> None:
        """Raise OrderRejected if the price is outside the band.
        No band configured => no restriction."""
        band = self._bands.get(symbol)
        if band is None:
            return
        if price < band.lower or price > band.upper:
            raise OrderRejected(
                f"{symbol} price {price} outside band "
                f"[{band.lower}, {band.upper}] (ref {band.reference})"
            )
