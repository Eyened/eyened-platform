"""Bootstrap the first administrator.

There is no administrator today: ``Creator.Role`` is NULL on all 74 rows and
the ``init_admin`` referenced at ``server/routes/auth.py`` was never written.
This is doubly load-bearing -- it also gates everyday local development, where
``EYENED_API_PUBLIC_AUTH_DISABLED=true`` resolves the ``admin_username``
account, which is a data superuser *only if that account is an administrator*.
"""
from __future__ import annotations

import enum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..creator import Creator
from ..utils.db_users import disable_password, hash_password, verify_password

__all__ = ["BootstrapOutcome", "count_admins", "ensure_admin"]


class BootstrapOutcome(str, enum.Enum):
    created = "created"
    promoted = "promoted"
    reactivated = "reactivated"
    unchanged = "unchanged"


def count_admins(session: Session) -> int:
    """Active administrators. Deactivated ones cannot make requests, so they do
    not count towards the last-admin guard."""
    return int(
        session.scalar(
            select(func.count())
            .select_from(Creator)
            .where(Creator.IsAdmin.is_(True), Creator.Inactive.is_(False))
        )
        or 0
    )


def ensure_admin(
    session: Session,
    username: str,
    password: str | None,
    *,
    reactivate: bool = False,
) -> tuple[Creator, BootstrapOutcome]:
    """Create or promote ``username`` to administrator, idempotently.

    Flushes without committing: ``get_db`` owns the request transaction, so an
    inner commit would end it from inside a dependency.

    ``password=None`` means password login is disabled for a new account and
    **left alone** for an existing one -- re-running ``init-admin`` without a
    password must not lock the account out. ``reactivate`` is opt-in so a
    routine bootstrap cannot silently undo a deliberate deactivation.
    """
    creator = session.scalars(
        select(Creator).where(Creator.CreatorName == username)
    ).first()

    if creator is None:
        creator = Creator(
            CreatorName=username,
            IsHuman=True,
            IsAdmin=True,
            Inactive=False,
            PasswordHash=hash_password(password) if password else disable_password(None),
        )
        session.add(creator)
        session.flush()
        return creator, BootstrapOutcome.created

    outcome = BootstrapOutcome.unchanged
    if not creator.IsAdmin:
        creator.IsAdmin = True
        outcome = BootstrapOutcome.promoted
    # Only re-hash when the supplied password does not already verify: hashing
    # is salted, so an unconditional re-hash writes a different string every
    # time and would report a change on an unchanged account.
    if password and not (
        creator.PasswordHash and verify_password(password, creator.PasswordHash)
    ):
        creator.PasswordHash = hash_password(password)
        if outcome is BootstrapOutcome.unchanged:
            outcome = BootstrapOutcome.promoted
    if reactivate and creator.Inactive:
        creator.Inactive = False
        outcome = BootstrapOutcome.reactivated
    session.flush()
    return creator, outcome
