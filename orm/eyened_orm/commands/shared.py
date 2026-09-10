from __future__ import annotations

import random
import string

import click
from eyened_orm import Database
from eyened_orm.authz.scope import AccessScope


def get_database(*, confirmation: bool = False) -> Database:
    database = Database()
    db_config = database.database_settings
    print(
        f"Connected to database {db_config.database} on {db_config.host}:{db_config.port}"
    )

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
