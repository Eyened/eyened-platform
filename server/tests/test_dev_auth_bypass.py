"""The dev bypass resolves the configured account by name every request,
falling back to ensure_admin only when the row is missing or not an admin.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


class _Creator:
    def __init__(
        self, creator_id: int = 7, inactive: bool = False, is_admin: bool = True
    ) -> None:
        self.CreatorID = creator_id
        self.CreatorName = "admin"
        self.Inactive = inactive
        self.IsAdmin = is_admin


class _Scalars:
    def __init__(self, result) -> None:
        self._result = result

    def first(self):
        return self._result


class _Session:
    def __init__(self, creator: _Creator | None) -> None:
        self._creator = creator
        self.lookups = 0

    def scalars(self, _stmt):
        self.lookups += 1
        return _Scalars(self._creator)


@pytest.fixture()
def cu(monkeypatch):
    import server.services.current_user as cu

    # Settings sets model_config frozen=True, so a field cannot be patched --
    # monkeypatch.setattr on cu.settings.public_auth_disabled raises
    # ValidationError. Replace the whole object on the module instead.
    monkeypatch.setattr(
        cu,
        "settings",
        SimpleNamespace(public_auth_disabled=True, admin_username="admin"),
    )
    return cu


def test_existing_active_admin_skips_ensure_admin_and_is_read_every_request(
    cu, monkeypatch
):
    """No write path runs once the account already qualifies; the read repeats."""

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("ensure_admin must not run for an existing admin")

    monkeypatch.setattr(cu, "ensure_admin", _fail_if_called)
    session = _Session(_Creator())

    for _ in range(5):
        user = cu.get_current_user(session=session)
        assert user.id == 7

    assert session.lookups == 5


def test_a_deactivated_account_is_rejected(cu, monkeypatch):
    """Found and already admin, but Inactive still 401s."""
    from fastapi import HTTPException

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("ensure_admin must not run for an already-admin account")

    monkeypatch.setattr(cu, "ensure_admin", _fail_if_called)
    session = _Session(_Creator(inactive=True))

    with pytest.raises(HTTPException) as exc:
        cu.get_current_user(session=session)
    assert exc.value.status_code == 401


def test_a_missing_account_still_bootstraps(cu, monkeypatch):
    """No row by that name yet: ensure_admin creates and promotes it."""
    calls = {"n": 0}
    creator = _Creator()

    def _fake_ensure_admin(session, username, password):
        calls["n"] += 1
        return creator, None

    monkeypatch.setattr(cu, "ensure_admin", _fake_ensure_admin)
    session = _Session(None)

    user = cu.get_current_user(session=session)

    assert calls["n"] == 1
    assert user.id == creator.CreatorID
