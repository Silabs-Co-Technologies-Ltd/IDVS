"""Password and KBI answer hashing helpers.

The deployed project uses bcrypt when the dependency is installed. A PBKDF2-SHA256
fallback keeps local tests and offline demonstrations operational on machines
where bcrypt wheels have not yet been installed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

try:
    import bcrypt
except ImportError:  # pragma: no cover - depends on deployment environment
    bcrypt = None

PBKDF2_PREFIX = "pbkdf2_sha256$"


def normalize_secret(value: str) -> str:
    return " ".join(value.strip().lower().split())


def hash_secret(value: str) -> str:
    normalized = normalize_secret(value).encode()
    if bcrypt is not None:
        return bcrypt.hashpw(normalized, bcrypt.gensalt()).decode()
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", normalized, salt, 390_000)
    return PBKDF2_PREFIX + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_secret(value: str, hashed: str) -> bool:
    if not value or not hashed:
        return False
    normalized = normalize_secret(value).encode()
    if hashed.startswith(PBKDF2_PREFIX):
        _, salt_b64, digest_b64 = hashed.split("$", 2)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", normalized, base64.b64decode(salt_b64), 390_000)
        return hmac.compare_digest(actual, expected)
    if bcrypt is None:
        return False
    return bcrypt.checkpw(normalized, hashed.encode())
