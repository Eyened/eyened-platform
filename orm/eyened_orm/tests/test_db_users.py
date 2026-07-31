from eyened_orm import Creator, SystemRole, is_system_admin
from eyened_orm.utils.db_users import create_user, ensure_admin
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401


def test_create_user_flushes_but_does_not_commit(session):
    """create_user assigns a PK via flush but leaves the transaction open for the caller."""
    user = create_user(session, "alice", "pw")
    assert user.CreatorID is not None            # flushed
    assert session.in_transaction()              # not committed
    session.rollback()
    assert session.query(Creator).filter_by(CreatorName="alice").count() == 0


def test_create_user_defaults_to_no_system_role(session):
    """/auth/register and OIDC auto-provision call create_user without `role`;
    they must keep producing Role=NULL or self-service signup escalates."""
    user = create_user(session, "self-signup", "pw")
    assert user.Role is None


def test_create_user_can_set_a_system_role(session):
    """The one in-band writer of Creator.Role, used by ensure_admin."""
    user = create_user(session, "boss", "pw", role=SystemRole.system_admin)
    assert user.Role == SystemRole.system_admin


def test_ensure_admin_creates_an_admin_when_absent(session):
    """Bootstrap on a fresh database: no admin exists, so one is created."""
    admin = ensure_admin(session, "admin", "pw")
    assert admin.CreatorID is not None
    assert is_system_admin(admin) is True
    assert admin.Inactive is False


def test_ensure_admin_promotes_an_existing_account(session):
    """The named account already exists as a plain user (Role=NULL on all 74
    production rows) -- promote it in place rather than failing on the username."""
    existing = create_user(session, "admin", "pw")
    assert existing.Role is None

    admin = ensure_admin(session, "admin", "pw")
    assert admin.CreatorID == existing.CreatorID
    assert is_system_admin(admin) is True
    assert session.query(Creator).filter_by(CreatorName="admin").count() == 1


def test_ensure_admin_reactivates_a_deactivated_admin(session):
    """Once P4 makes Inactive refuse logins, the one command that exists to
    recover a deployment must be able to recover the case where its only admin
    was deactivated (the last-admin guard that would prevent it is P7)."""
    existing = create_user(session, "admin", "pw", role=SystemRole.system_admin)
    existing.Inactive = True
    session.flush()

    admin = ensure_admin(session, "admin", "pw")
    assert admin.Inactive is False
    assert is_system_admin(admin) is True


def test_ensure_admin_is_idempotent(session):
    """Re-running the bootstrap is safe and rewrites nothing."""
    first = ensure_admin(session, "admin", "pw")
    hash_before = first.PasswordHash
    session.commit()

    second = ensure_admin(session, "admin", "different-password")
    assert second.CreatorID == first.CreatorID
    # An already-correct admin is left alone: the password is NOT reset, so
    # re-running the bootstrap can never lock the real admin out of their account.
    assert second.PasswordHash == hash_before


def test_ensure_admin_does_not_commit(session):
    """get_db owns the request transaction, so a commit here would end it from
    inside a dependency. The caller commits."""
    ensure_admin(session, "admin", "pw")
    assert session.in_transaction()
    session.rollback()
    assert session.query(Creator).filter_by(CreatorName="admin").count() == 0


def test_create_user_writes_role_as_a_plain_int(session):
    """Creator.Role is an untyped Integer with no bind processor, and IntEnum is
    absent from pymysql's exact-type encoders -- so an un-coerced member falls
    through to the *string* encoder and the driver sends '1' rather than 1.

    `type(...) is int` is the only assertion that can see this. `==` is True for
    both forms, and isinstance() passes because IntEnum subclasses int. SQLite
    accepts int subclasses natively, so no behavioural test can catch it either:
    this is the whole guard for a MySQL-only failure mode.
    """
    user = create_user(session, "boss", "pw", role=SystemRole.system_admin)

    assert type(user.Role) is int


def test_ensure_admin_promotes_with_a_plain_int(session):
    """The same coercion on the promote branch, which is a second write site."""
    create_user(session, "admin", "pw")

    admin = ensure_admin(session, "admin", "pw")

    assert type(admin.Role) is int
