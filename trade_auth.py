"""Trade password: identity confirmation at order-placement time.

Separate from login authentication. bcrypt hashing, lockout after 5 failed
attempts for 60 seconds.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

import bcrypt

MAX_FAILURES = 5
LOCK_SECONDS = 60


class TradeAuthError(Exception):
    pass


class TradePasswordNotSet(TradeAuthError):
    pass


class InvalidTradePassword(TradeAuthError):
    pass


class TradeAuthLocked(TradeAuthError):
    pass


@dataclass
class _Entry:
    pw_hash: bytes
    failures: int = 0
    locked_until: float = 0.0


class TradeAuth:
    def __init__(self, clock=None):
        self._clock = clock or time.time
        self._entries: Dict[str, _Entry] = {}

    def set_password(self, user: str, password: str) -> None:
        if not password:
            raise InvalidTradePassword("password required")
        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        self._entries[user] = _Entry(pw_hash=pw_hash)

    def is_set(self, user: str) -> bool:
        return user in self._entries

    def verify(self, user: str, password: str) -> bool:
        entry = self._entries.get(user)
        if entry is None:
            raise TradePasswordNotSet(user)
        now = self._clock()
        if entry.locked_until and now < entry.locked_until:
            raise TradeAuthLocked(
                f"locked for {int(entry.locked_until - now)}s after too many attempts"
            )
        if bcrypt.checkpw(password.encode("utf-8"), entry.pw_hash):
            entry.failures = 0
            entry.locked_until = 0.0
            return True
        entry.failures += 1
        if entry.failures >= MAX_FAILURES:
            entry.locked_until = now + LOCK_SECONDS
            entry.failures = 0
            raise TradeAuthLocked("too many failed attempts; trade password locked")
        raise InvalidTradePassword("invalid trade password")
