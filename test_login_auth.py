import pytest

from login_auth import (
    AccountLocked,
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidEmail,
    LoginAuth,
    normalize_email,
)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_email_normalization():
    assert normalize_email("  USER@Example.COM ") == "user@example.com"


def test_invalid_email_rejected():
    with pytest.raises(InvalidEmail):
        normalize_email("not-an-email")


def test_register_and_login():
    auth = LoginAuth(secret_key="test-secret")
    auth.register("a@b.com", "pw")
    token = auth.login("a@b.com", "pw")
    assert auth.verify_token(token) == "a@b.com"


def test_duplicate_registration():
    auth = LoginAuth(secret_key="test-secret")
    auth.register("a@b.com", "pw")
    with pytest.raises(EmailAlreadyRegistered):
        auth.register("A@B.com", "pw2")


def test_wrong_password():
    auth = LoginAuth(secret_key="test-secret")
    auth.register("a@b.com", "pw")
    with pytest.raises(InvalidCredentials):
        auth.login("a@b.com", "wrong")


def test_lockout_after_five_failures():
    clock = FakeClock()
    auth = LoginAuth(secret_key="test-secret", clock=clock)
    auth.register("a@b.com", "pw")
    for _ in range(4):
        with pytest.raises(InvalidCredentials):
            auth.login("a@b.com", "wrong")
    # 5th failure locks
    with pytest.raises(AccountLocked):
        auth.login("a@b.com", "wrong")
    # still locked even with correct password
    with pytest.raises(AccountLocked):
        auth.login("a@b.com", "pw")
    # after 5 minutes it unlocks
    clock.t += 5 * 60 + 1
    token = auth.login("a@b.com", "pw")
    assert auth.verify_token(token) == "a@b.com"


def test_secret_key_required():
    with pytest.raises(ValueError):
        LoginAuth(secret_key="")


def test_token_expiry():
    clock = FakeClock()
    auth = LoginAuth(secret_key="test-secret", token_ttl=10, clock=clock)
    auth.register("a@b.com", "pw")
    token = auth.login("a@b.com", "pw")
    clock.t += 20
    with pytest.raises(InvalidCredentials):
        auth.verify_token(token)
