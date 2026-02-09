from __future__ import annotations

from eyened_orm import Database


def get_database() -> Database:
    database = Database()
    db_config = database.database_settings
    print(
        f"Connected to database {db_config.database} on {db_config.host}:{db_config.port}"
    )
    return database
