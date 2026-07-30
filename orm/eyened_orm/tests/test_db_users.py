from eyened_orm import Creator
from eyened_orm.utils.db_users import create_user
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401


def test_create_user_flushes_but_does_not_commit(session):
    """create_user assigns a PK via flush but leaves the transaction open for the caller."""
    user = create_user(session, "alice", "pw")
    assert user.CreatorID is not None            # flushed
    assert session.in_transaction()              # not committed
    session.rollback()
    assert session.query(Creator).filter_by(CreatorName="alice").count() == 0
