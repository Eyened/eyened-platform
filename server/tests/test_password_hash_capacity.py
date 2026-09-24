"""Concurrent Argon2 hashing is bounded, and the bound is wired into login.

Argon2 costs 64 MiB per hash here. On the event loop the cost was serialized by
accident; in the threadpool it is not, and /auth/login needs no credentials to
reach. These tests pin both halves: the gate bounds, and the login path uses it.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

from eyened_orm import Creator
from eyened_orm.utils.db_users import hash_password

from server.config import settings
from server.services import password_hashing
from server.services.password_hashing import password_hash_capacity


def _max_concurrent(gate, workers: int) -> int:
    """Drive `workers` threads through `gate` at once; return the peak overlap."""
    peak = 0
    current = 0
    lock = threading.Lock()
    released = threading.Barrier(workers)

    def run() -> None:
        nonlocal peak, current
        released.wait()
        with gate():
            with lock:
                current += 1
                peak = max(peak, current)
            time.sleep(0.02)
            with lock:
                current -= 1

    threads = [threading.Thread(target=run) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return peak


def test_gate_bounds_concurrent_hashing():
    """Peak overlap never exceeds the configured limit."""
    limit = settings.password_hash_concurrency
    assert _max_concurrent(password_hash_capacity, limit * 4) <= limit


def test_the_gate_can_fail():
    """Negative control: the same driver observes real overlap without the gate.

    Without this, a gate that never admitted anyone -- or a driver whose threads
    never overlapped -- would satisfy the bound above for the wrong reason.
    """

    @contextmanager
    def ungated():
        yield

    limit = settings.password_hash_concurrency
    assert _max_concurrent(ungated, limit * 4) > limit


def test_login_holds_a_hashing_slot(client, session, monkeypatch, signed_jwts):
    """The gate is wired into the login path, not merely defined beside it."""
    session.add(
        Creator(
            CreatorName="gated-user",
            PasswordHash=hash_password("pw"),
            IsHuman=True,
        )
    )
    session.commit()

    real = password_hashing._gate
    acquisitions = []

    class _Counting:
        def __enter__(self):
            acquisitions.append(1)
            return real.__enter__()

        def __exit__(self, *exc):
            return real.__exit__(*exc)

    monkeypatch.setattr(password_hashing, "_gate", _Counting())

    response = client.post(
        "/auth/login", json={"username": "gated-user", "password": "pw"}
    )

    assert response.status_code == 200
    assert acquisitions, (
        "login verified an Argon2 hash without holding a hashing slot -- the "
        "gate exists but the login path does not go through it"
    )
