"""The dev bypass bootstraps once, not once per request.

ensure_admin is a write path. Running it per request skews any local
measurement and does work the second request cannot need. The deactivation
check must survive, so the cache holds an id and the per-request path stays a
lookup.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


class _Creator:
    def __init__(self, creator_id: int = 7, inactive: bool = False) -> None:
        self.CreatorID = creator_id
        self.CreatorName = "admin"
        self.Inactive = inactive


class _Session:
    def __init__(self, creator: _Creator) -> None:
        self._creator = creator
        self.gets = 0

    def get(self, _model, _pk):
        self.gets += 1
        return self._creator


@pytest.fixture()
def bypass(monkeypatch):
    import server.services.current_user as cu

    # Settings sets model_config frozen=True, so a field cannot be patched --
    # monkeypatch.setattr on cu.settings.public_auth_disabled raises
    # ValidationError. Replace the whole object on the module instead.
    monkeypatch.setattr(
        cu,
        "settings",
        SimpleNamespace(public_auth_disabled=True, admin_username="admin"),
    )
    monkeypatch.setattr(cu, "_BYPASS_CREATOR_ID", None, raising=False)
    calls = {"n": 0}
    creator = _Creator()

    def _fake_ensure_admin(session, username, password):
        calls["n"] += 1
        return creator, None

    monkeypatch.setattr(cu, "ensure_admin", _fake_ensure_admin)
    return cu, calls, _Session(creator)


def test_ensure_admin_runs_once_across_many_requests(bypass):
    """The write happens on the first request only."""
    cu, calls, session = bypass
    import anyio

    async def call():
        return await cu.get_current_user(session=session)

    for _ in range(5):
        user = anyio.run(call)
        assert user.id == 7

    assert calls["n"] == 1, f"ensure_admin ran {calls['n']} times, expected 1"
    assert session.gets == 4, "requests after the first must still look the row up"


def test_a_deactivated_bootstrap_account_is_rejected(bypass):
    """Caching an id must not cache the right to use it."""
    import anyio
    from fastapi import HTTPException

    cu, _, session = bypass
    anyio.run(lambda: cu.get_current_user(session=session))  # populate the cache
    session._creator.Inactive = True

    with pytest.raises(HTTPException) as exc:
        anyio.run(lambda: cu.get_current_user(session=session))
    assert exc.value.status_code == 401
