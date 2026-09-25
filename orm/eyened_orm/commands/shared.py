from __future__ import annotations

import random
import string

import click
from sqlalchemy import inspect

from eyened_orm import Database
from eyened_orm.audit_writer import AuditWriter
from eyened_orm.authz.account_admin import AccountAdministration
from eyened_orm.authz.actor import TrustedPath
from eyened_orm.authz.scope import AccessScope
from eyened_orm.repositories import CreatorRepository
from sqlalchemy.orm import Session


def _has_tables(database: Database) -> bool:
    """
    Whether the target database contains any tables.

    An unreadable schema is not evidence of an empty one, so a failed
    inspection reports True and the caller falls back to prompting.

    Deliberately broad: caught as plain `Exception`, not `SQLAlchemyError`.
    A driver-level or otherwise-unwrapped error is just as undiagnosable as
    a SQLAlchemy one, and an undiagnosable database must be treated as
    populated -- the contract is "failing inspection falls back to
    prompting", not "failing inspection *in a way SQLAlchemy recognizes*
    falls back to prompting". Do not narrow this to SQLAlchemyError.
    """
    try:
        return bool(inspect(database.engine).get_table_names())
    except Exception as exc:
        print(f"Could not inspect the target database ({exc}).")
        return True


def get_database(*, confirmation: bool = False) -> Database:
    database = Database()
    db_config = database.database_settings
    print(
        f"Connected to database {db_config.database} on {db_config.host}:{db_config.port}"
    )

    # The risk these commands carry is a property of the database's state, not
    # of the command: nothing here can destroy an empty database, while
    # stamp_alembic_head on a populated, already-versioned one silently skips
    # migrations. So gate on state, and say so when the gate does not apply.
    if confirmation and not _has_tables(database):
        print(
            f"Target database {db_config.database} on "
            f"{db_config.host}:{db_config.port} has no tables "
            "— proceeding without confirmation."
        )
        confirmation = False

    if confirmation:
        print("\n" + "=" * 60)
        print(
            f"Target database: {db_config.database} on {db_config.host}:{db_config.port}"
        )
        print("=" * 60)

        confirmation_code = "".join(random.choices(string.ascii_uppercase, k=4))
        print(f"\nDo you want to proceed? Type '{confirmation_code}' to confirm:")

        user_input = click.prompt("", type=str)
        if user_input != confirmation_code:
            raise click.ClickException(
                "Confirmation code does not match. Operation cancelled."
            )

    return database


def admin_scope_for_cli() -> AccessScope:
    """The unbounded scope the ``eorm`` repositories run under.

    v0.3 places the CLI outside RBAC enforcement as a trusted path, so this
    grants it nothing it did not already have: ``get_database()`` above
    authenticates nobody, and whoever runs the binary already opens a
    ``Database()`` straight from config.

    Confined to this one function on purpose. ``AccessScope.trusted`` is pinned
    by an exact-set allow-list in ``server/tests/test_escalation_paths.py``, and
    building the scope at each command would grow that list by every module that
    administers anything. One entry is reviewable; ten is a list nobody reads.

    ``AccessScope.trusted()``, not ``utils/factories.admin_scope()``: the
    factory is test support, and importing it into a production path would put
    test scaffolding in the CLI's import graph.
    """
    return AccessScope.trusted(username="eorm")


def account_admin(session: Session, actor: TrustedPath) -> AccountAdministration:
    """Build the account administration a command is attributed to."""
    return AccountAdministration(
        CreatorRepository(session, scope=admin_scope_for_cli()),
        audit=AuditWriter(session),
        actor=actor,
    )
