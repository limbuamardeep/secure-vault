import os

import pytest
from app.crypto import decrypt, derive_kek, encrypt
from cryptography.exceptions import InvalidTag


def test_roundtrip():
    key = os.urandom(32)
    assert decrypt(key, encrypt(key, b"hunter2")) == b"hunter2"


def test_nonce_is_random():
    key = os.urandom(32)
    assert encrypt(key, b"same") != encrypt(key, b"same")


def test_tamper_detected():
    key = os.urandom(32)
    blob = bytearray(encrypt(key, b"secret"))
    blob[-1] ^= 1
    with pytest.raises(InvalidTag):
        decrypt(key, bytes(blob))


def test_wrong_key_fails():
    blob = encrypt(os.urandom(32), b"secret")
    with pytest.raises(InvalidTag):
        decrypt(os.urandom(32), blob)


def test_kek_deterministic():
    salt = os.urandom(16)
    assert derive_kek("pw", salt) == derive_kek("pw", salt)
    assert derive_kek("pw", salt) != derive_kek("pw2", salt)