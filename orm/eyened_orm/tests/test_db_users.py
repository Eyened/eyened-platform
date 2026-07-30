from eyened_orm import Creator, SystemRole
from eyened_orm.utils.db_users import create_user
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
