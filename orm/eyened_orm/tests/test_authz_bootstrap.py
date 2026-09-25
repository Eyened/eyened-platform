"""ensure_admin: idempotent, flush-only, and safe with no password."""
from __future__ import annotations

import pytest

from eyened_orm import Creator
from eyened_orm.authz.bootstrap import BootstrapOutcome, count_admins, ensure_admin
from eyened_orm.utils.db_users import WeakPasswordError, hash_password, verify_password
from eyened_orm.utils.factories import make_creator


def test_creates_an_administrator_when_none_exists(session):
    creator, outcome = ensure_admin(session, "root", "correct horse battery staple")
    assert outcome is BootstrapOutcome.created
    assert creator.IsAdmin is True
    assert verify_password("correct horse battery staple", creator.PasswordHash)


def test_promotes_an_existing_plain_user(session):
    make_creator(session, "root")
    creator, outcome = ensure_admin(session, "root", None)
    assert outcome is BootstrapOutcome.promoted
    assert creator.IsAdmin is True


def test_is_idempotent(session):
    ensure_admin(session, "root", "correct horse battery staple")
    _, outcome = ensure_admin(session, "root", "correct horse battery staple")
    assert outcome is BootstrapOutcome.unchanged


def test_a_none_password_disables_password_login_rather_than_erroring(session):
    """The dev bypass never posts credentials, so a password is optional."""
    creator, _ = ensure_admin(session, "root", None)
    assert creator.PasswordHash is not None
    assert verify_password("anything", creator.PasswordHash) is False


def test_a_none_password_does_not_overwrite_an_existing_one(session):
    """Re-running init-admin without --password must not lock the account out."""
    ensure_admin(session, "root", "correct horse battery staple")
    creator, _ = ensure_admin(session, "root", None)
    assert verify_password("correct horse battery staple", creator.PasswordHash)


def test_flushes_without_committing(session):
    """get_db owns the request transaction; an inner commit would end it."""
    from sqlalchemy import select

    ensure_admin(session, "root", "correct horse battery staple")
    assert session.in_transaction()
    session.rollback()
    assert (
        session.scalars(select(Creator).where(Creator.CreatorName == "root")).first()
        is None
    )


def test_a_password_reset_on_an_existing_administrator_is_not_a_promotion(session):
    """The one event that must not borrow ``promoted``.

    ``IsAdmin`` is already True and does not move; the only thing that changes
    is the platform superuser's credential. Reporting that as ``promoted``
    makes the audit row assert a privilege change that did not happen and
    leaves the change that did happen recorded nowhere.
    """
    creator, _ = ensure_admin(session, "root", "correct horse battery staple")
    assert creator.IsAdmin is True

    _, outcome = ensure_admin(session, "root", "rotated horse battery staple")
    assert outcome is BootstrapOutcome.password_reset
    assert creator.IsAdmin is True
    assert verify_password("rotated horse battery staple", creator.PasswordHash)


def test_a_promotion_that_also_sets_a_password_reports_both(session):
    """Both-at-once is its own result: a single-valued ``promoted`` here would
    lose the credential change, and a single-valued ``password_reset`` would
    lose the grant of administrator."""
    make_creator(session, "root")
    creator, outcome = ensure_admin(session, "root", "correct horse battery staple")
    assert outcome is BootstrapOutcome.promoted_and_password_reset
    assert creator.IsAdmin is True
    assert verify_password("correct horse battery staple", creator.PasswordHash)


def test_reactivate_is_opt_in(session):
    creator, _ = ensure_admin(session, "root", "correct horse battery staple")
    creator.Inactive = True
    session.flush()

    _, outcome = ensure_admin(session, "root", "correct horse battery staple")
    assert outcome is BootstrapOutcome.unchanged
    assert creator.Inactive is True

    _, outcome = ensure_admin(session, "root", "correct horse battery staple", reactivate=True)
    assert outcome is BootstrapOutcome.reactivated
    assert creator.Inactive is False


def test_a_password_reset_revokes_the_legacy_password_column(session):
    """AuthService falls through to the legacy Password column when PasswordHash
    misses; leaving it set after a reset would let the old credential keep
    authenticating."""
    root = make_creator(session, "root")
    root.IsAdmin = True
    root.PasswordHash = hash_password("s3cret")
    root.Password = b"0" * 32
    session.flush()

    _, outcome = ensure_admin(session, "root", "correct horse battery staple")
    assert outcome is BootstrapOutcome.password_reset
    assert root.Password is None


def test_count_admins_ignores_deactivated_administrators(session):
    """The last-admin guard must not count someone who cannot make requests."""
    _, _ = ensure_admin(session, "root", None)
    second, _ = ensure_admin(session, "root2", None)
    assert count_admins(session) == 2
    second.Inactive = True
    session.flush()
    assert count_admins(session) == 1


def test_the_policy_applies_only_to_a_password_being_set(session):
    """A short existing password keeps verifying; rotating to another short one is refused."""
    root = make_creator(session, "root")
    root.IsAdmin = True
    root.PasswordHash = hash_password("s3cret")
    session.flush()

    _, outcome = ensure_admin(session, "root", "s3cret")
    assert outcome is BootstrapOutcome.unchanged

    with pytest.raises(WeakPasswordError, match="at least 15"):
        ensure_admin(session, "root", "rotated")
