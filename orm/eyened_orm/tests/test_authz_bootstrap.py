"""ensure_admin: idempotent, flush-only, and safe with no password."""
from __future__ import annotations

from eyened_orm import Creator
from eyened_orm.authz.bootstrap import BootstrapOutcome, count_admins, ensure_admin
from eyened_orm.utils.db_users import verify_password
from eyened_orm.utils.factories import make_creator


def test_creates_an_administrator_when_none_exists(session):
    creator, outcome = ensure_admin(session, "root", "s3cret")
    assert outcome is BootstrapOutcome.created
    assert creator.IsAdmin is True
    assert verify_password("s3cret", creator.PasswordHash)


def test_promotes_an_existing_plain_user(session):
    make_creator(session, "root")
    creator, outcome = ensure_admin(session, "root", None)
    assert outcome is BootstrapOutcome.promoted
    assert creator.IsAdmin is True


def test_is_idempotent(session):
    ensure_admin(session, "root", "s3cret")
    _, outcome = ensure_admin(session, "root", "s3cret")
    assert outcome is BootstrapOutcome.unchanged


def test_a_none_password_disables_password_login_rather_than_erroring(session):
    """The dev bypass never posts credentials, so a password is optional."""
    creator, _ = ensure_admin(session, "root", None)
    assert creator.PasswordHash is not None
    assert verify_password("anything", creator.PasswordHash) is False


def test_a_none_password_does_not_overwrite_an_existing_one(session):
    """Re-running init-admin without --password must not lock the account out."""
    ensure_admin(session, "root", "s3cret")
    creator, _ = ensure_admin(session, "root", None)
    assert verify_password("s3cret", creator.PasswordHash)


def test_flushes_without_committing(session):
    """get_db owns the request transaction; an inner commit would end it."""
    from sqlalchemy import select

    ensure_admin(session, "root", "s3cret")
    assert session.in_transaction()
    session.rollback()
    assert (
        session.scalars(select(Creator).where(Creator.CreatorName == "root")).first()
        is None
    )


def test_reactivate_is_opt_in(session):
    creator, _ = ensure_admin(session, "root", "s3cret")
    creator.Inactive = True
    session.flush()

    _, outcome = ensure_admin(session, "root", "s3cret")
    assert outcome is BootstrapOutcome.unchanged
    assert creator.Inactive is True

    _, outcome = ensure_admin(session, "root", "s3cret", reactivate=True)
    assert outcome is BootstrapOutcome.reactivated
    assert creator.Inactive is False


def test_count_admins_ignores_deactivated_administrators(session):
    """The last-admin guard must not count someone who cannot make requests."""
    _, _ = ensure_admin(session, "root", None)
    second, _ = ensure_admin(session, "root2", None)
    assert count_admins(session) == 2
    second.Inactive = True
    session.flush()
    assert count_admins(session) == 1
