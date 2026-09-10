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
    """What ``ensure_admin`` actually did, one member per distinguishable event.

    A promotion and a password reset are separate members, and doing both in
    one call is a third: the caller audits from this value, and a single
    borrowed name would make the compliance record assert a privilege change
    that did not happen (or lose the credential change that did).
    """

    created = "created"
    promoted = "promoted"
    password_reset = "password_reset"
    promoted_and_password_reset = "promoted_and_password_reset"
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

    promoted = False
    if not creator.IsAdmin:
        creator.IsAdmin = True
        promoted = True
    # Only re-hash when the supplied password does not already verify: hashing
    # is salted, so an unconditional re-hash writes a different string every
    # time and would report a change on an unchanged account.
    password_reset = bool(password) and not (
        creator.PasswordHash and verify_password(password, creator.PasswordHash)
    )
    if password_reset:
        creator.PasswordHash = hash_password(password)

    # Tracked as two booleans and collapsed here, rather than one variable
    # overwritten twice: the two events are independent, and the previous
    # single-valued assignment could only report whichever ran last.
    if promoted and password_reset:
        outcome = BootstrapOutcome.promoted_and_password_reset
    elif promoted:
        outcome = BootstrapOutcome.promoted
    elif password_reset:
        outcome = BootstrapOutcome.password_reset
    else:
        outcome = BootstrapOutcome.unchanged
    if reactivate and creator.Inactive:
        creator.Inactive = False
        outcome = BootstrapOutcome.reactivated
    session.flush()
    return creator, outcome
