from __future__ import annotations

import hashlib


def sha256_bytes(data: bytes) -> bytes:
    """32-byte digest for ``ImageStorage.Hash`` (``BINARY(32)``)."""
    return hashlib.sha256(data).digest()


def md5_hex(data: bytes) -> str:
    """Hex string for ``ImageStorage.Checksum``."""
    return hashlib.md5(data, usedforsecurity=False).hexdigest()
