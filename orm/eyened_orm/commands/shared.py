from __future__ import annotations

import random
import string

import click
from sqlalchemy import inspect

from eyened_orm import Database


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
    falls back to prompting". Do not narrow this back to SQLAlchemyError.
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
