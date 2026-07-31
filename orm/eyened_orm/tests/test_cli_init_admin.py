"""The bootstrap CLI's wiring: prompt -> ensure_admin -> commit.

``get_database`` is replaced with a stand-in yielding the test's SQLite session,
mirroring server/tests/conftest.py's ``_SessionBoundDatabase``: the point is to
exercise the real command body, not a re-implementation of it.
"""
from contextlib import contextmanager

from click.testing import CliRunner

from eyened_orm import Creator, SystemRole, is_system_admin
from eyened_orm.utils.db_users import create_user
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401


class _SessionBoundDatabase:
    def __init__(self, session) -> None:
        self._session = session

    @contextmanager
    def get_session(self):
        yield self._session


def test_init_admin_creates_and_commits_a_system_admin(session, monkeypatch):
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))

    result = CliRunner().invoke(
        cli.eorm, ["init-admin"], input="admin\nsecret\nsecret\n"
    )

    assert result.exit_code == 0, result.output
    admin = session.query(Creator).filter_by(CreatorName="admin").one()
    assert is_system_admin(admin) is True

    # Committed, not merely flushed -- the CLI is the transaction owner, so a
    # rollback afterwards must not take the admin with it. `in_transaction()` would
    # not prove this: the query above already opened a fresh transaction.
    session.rollback()
    assert session.query(Creator).filter_by(CreatorName="admin").count() == 1


def test_init_admin_is_idempotent(session, monkeypatch):
    """Re-running on an already-active admin must be silent and fast: no
    confirmation, and no message claiming a promotion that did not happen."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))

    runner = CliRunner()
    first = runner.invoke(cli.eorm, ["init-admin"], input="admin\nsecret\nsecret\n")
    assert first.exit_code == 0, first.output
    assert "Created system admin" in first.output

    result = runner.invoke(cli.eorm, ["init-admin"], input="admin\nsecret\nsecret\n")

    assert result.exit_code == 0, result.output
    assert session.query(Creator).filter_by(CreatorName="admin").count() == 1
    assert "already a system admin" in result.output
    # The alarm must NOT fire on the benign path -- that is what taught
    # operators to ignore it.
    assert "PRE-EXISTING" not in result.output


def test_init_admin_confirms_before_promoting_a_pre_existing_account(
    session, monkeypatch
):
    """/auth/register is unauthenticated and admin_username defaults to 'admin',
    so a pre-existing account of that name may have been placed there by someone
    else -- and ensure_admin keeps its password. Answering 'y' promotes."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    create_user(session, "admin", "someone-elses-password")
    session.commit()

    result = CliRunner().invoke(
        cli.eorm, ["init-admin"], input="admin\nsecret\nsecret\ny\n"
    )

    assert result.exit_code == 0, result.output
    assert "PRE-EXISTING" in result.output
    # "PRE-EXISTING" alone also appears in the post-commit "Promoted
    # PRE-EXISTING account ..." report line, so it cannot distinguish
    # "the confirmation prompt was shown" from "no prompt, just the report".
    # "Promote this account?" is the prompt's closing question and appears
    # nowhere in any of the four outcome report lines -- asserting it pins
    # that click.confirm actually ran.
    assert "Promote this account?" in result.output
    admin = session.query(Creator).filter_by(CreatorName="admin").one()
    assert is_system_admin(admin) is True


def test_init_admin_aborts_the_promote_without_committing(session, monkeypatch):
    """Declining must leave the account exactly as it was. The prompt is before
    the commit precisely so that 'n' is a real veto rather than a notification --
    bootstrap never demotes, so a wrong promote is only undoable by hand."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    create_user(session, "admin", "someone-elses-password")
    session.commit()

    result = CliRunner().invoke(
        cli.eorm, ["init-admin"], input="admin\nsecret\nsecret\nn\n"
    )

    assert result.exit_code != 0
    session.rollback()
    admin = session.query(Creator).filter_by(CreatorName="admin").one()
    assert is_system_admin(admin) is False
    assert admin.Role is None


def test_init_admin_reactivates_a_deactivated_admin(session, monkeypatch):
    """The CLI passes reactivate=True -- a human running the recovery command is
    the consent. This is the path that recovers a deployment whose only admin
    was deactivated."""
    import eyened_orm.cli as cli

    monkeypatch.setattr(cli, "get_database", lambda *a, **k: _SessionBoundDatabase(session))
    existing = create_user(session, "admin", "pw", role=SystemRole.system_admin)
    existing.Inactive = True
    session.commit()

    result = CliRunner().invoke(
        cli.eorm, ["init-admin"], input="admin\nsecret\nsecret\n"
    )

    assert result.exit_code == 0, result.output
    assert "Reactivated" in result.output
    admin = session.query(Creator).filter_by(CreatorName="admin").one()
    assert admin.Inactive is False
