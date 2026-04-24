"""Smoke tests for the symmetric crypto wrapper."""
from __future__ import annotations

import pytest

from app.core.crypto import SecretCrypto


def test_round_trip_with_fernet_key() -> None:
    crypto = SecretCrypto("Zx3LrW5F0wKQnM4tGqGQwJfX7wQ2S0hJ8c8m1nP9b-c=")
    cipher = crypto.encrypt("sk-test-1234567890")
    assert cipher and cipher != "sk-test-1234567890"
    assert crypto.decrypt(cipher) == "sk-test-1234567890"


def test_round_trip_with_passphrase() -> None:
    """The crypto helper accepts arbitrary strings and derives a Fernet key."""
    crypto = SecretCrypto("not-a-fernet-key-but-still-fine")
    cipher = crypto.encrypt("hello world")
    assert crypto.decrypt(cipher) == "hello world"


def test_decrypt_invalid_token_returns_empty() -> None:
    """An invalid token must not crash callers; it returns an empty string."""
    crypto = SecretCrypto("any-key")
    assert crypto.decrypt("not-a-real-token") == ""


def test_encrypt_is_non_deterministic() -> None:
    """Fernet adds a random IV so two encryptions of the same value differ."""
    crypto = SecretCrypto("any-key")
    a = crypto.encrypt("same-value")
    b = crypto.encrypt("same-value")
    assert a != b
    assert crypto.decrypt(a) == "same-value"
    assert crypto.decrypt(b) == "same-value"


def test_different_keys_cannot_decrypt_each_other() -> None:
    a = SecretCrypto("key-a")
    b = SecretCrypto("key-b")
    cipher = a.encrypt("secret")
    # b cannot read a's ciphertext: should return empty (InvalidToken handled).
    assert b.decrypt(cipher) == ""


@pytest.mark.parametrize("key", ["", "a", "x" * 1024])
def test_extreme_key_lengths_are_handled(key: str) -> None:
    crypto = SecretCrypto(key)
    cipher = crypto.encrypt("payload")
    assert crypto.decrypt(cipher) == "payload"
