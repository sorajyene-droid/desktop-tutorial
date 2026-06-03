"""Login authentication.

Email registration (format check + lowercase normalisation), bcrypt password
hashing, account lockout after 5 failed attempts for 5 minutes, and JWT
issuance with an expiry. Email verification / 2FA are intentionally left as
extension points (hooks below) but not implemented.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import bcrypt
import jwt

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_FAILURES = 5
LOCK_SECONDS = 5 * 60  # 5 minutes


class AuthError(Exception):
    pass


class InvalidEmail(AuthError):
    pass


class EmailAlreadyRegistered(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class AccountLocked(AuthError):
    pass


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise InvalidEmail(f"invalid email format: {email!r}")
    return email


@dataclass
class _User:
    email: str
    pw_hash: bytes
    failures: int = 0
    locked_until: float = 0.0
    email_verified: bool = False


class LoginAuth:
    def __init__(self, secret_key: str, token_ttl: int = 3600, clock=None):
        if not secret_key:
            raise ValueError("secret_key is required (read it from the environment)")
        self._secret = secret_key
        self._ttl = token_ttl
        self._clock = clock or time.time
        self._users: Dict[str, _User] = {}

    # ----- registration --------------------------------------------------
    def register(self, email: str, password: str) -> str:
        email = normalize_email(email)
        if email in self._users:
            raise EmailAlreadyRegistered(email)
        if not password:
            raise InvalidCredentials("password required")
        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        self._users[email] = _User(email=email, pw_hash=pw_hash)
        return email

    def is_registered(self, email: str) -> bool:
        try:
            return normalize_email(email) in self._users
        except InvalidEmail:
            return False

    # ----- login ---------------------------------------------------------
    def login(self, email: str, password: str) -> str:
        email = normalize_email(email)
        user = self._users.get(email)
        now = self._clock()
        if user is None:
            # uniform error: do not leak which emails exist
            raise InvalidCredentials("invalid email or password")
        if user.locked_until and now < user.locked_until:
            raise AccountLocked(
                f"locked for {int(user.locked_until - now)}s after too many attempts"
            )
        if bcrypt.checkpw(password.encode("utf-8"), user.pw_hash):
            user.failures = 0
            user.locked_until = 0.0
            return self.issue_token(email)
        # failure
        user.failures += 1
        if user.failures >= MAX_FAILURES:
            user.locked_until = now + LOCK_SECONDS
            user.failures = 0
            raise AccountLocked("too many failed attempts; account locked")
        raise InvalidCredentials("invalid email or password")

    # ----- tokens --------------------------------------------------------
    def issue_token(self, email: str) -> str:
        now = int(self._clock())
        payload = {"sub": email, "iat": now, "exp": now + self._ttl}
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify_token(self, token: str) -> str:
        try:
            # Verify the signature with PyJWT, but check expiry against our own
            # (possibly injected) clock so behaviour is consistent in tests.
            payload = jwt.decode(
                token, self._secret, algorithms=["HS256"],
                options={"verify_exp": False},
            )
        except jwt.InvalidTokenError as e:
            raise InvalidCredentials("invalid token") from e
        if "exp" in payload and self._clock() >= payload["exp"]:
            raise InvalidCredentials("token expired")
        return payload["sub"]

    # ----- extension points (not implemented yet) -----------------------
    def mark_email_verified(self, email: str) -> None:
        email = normalize_email(email)
        if email in self._users:
            self._users[email].email_verified = True
