from __future__ import annotations

from pathlib import Path

from eyened_orm.data_access import load_storage_mounts


def read_storage_object_bytes(storage_backend_key: str, object_key: str) -> bytes:
    """
    Read an object from local storage using ``EYENED_STORAGE_MOUNTS``.

    Raises ``KeyError`` if the backend is not mounted, ``FileNotFoundError`` if
    the file is missing.
    """
    mounts = load_storage_mounts()
    root: Path | None = mounts.get(storage_backend_key)
    if root is None:
        raise KeyError(
            f"Storage backend {storage_backend_key!r} is not in EYENED_STORAGE_MOUNTS"
        )
    path = root / object_key
    return path.read_bytes()


def try_read_storage_object_bytes(
    storage_backend_key: str | None, object_key: str | None
) -> bytes | None:
    if not storage_backend_key or not object_key:
        return None
    try:
        return read_storage_object_bytes(storage_backend_key, object_key)
    except (KeyError, OSError, FileNotFoundError):
        return None
