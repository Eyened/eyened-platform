from __future__ import annotations

import random
import string

import click
from eyened_orm import Database


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
