from __future__ import annotations

from dotenv import load_dotenv

from eyened_orm import Database


def get_database(env: str) -> Database:
    load_dotenv(env)
    database = Database(env)
    db_config = database.config.database
    print(
        f"Connected to database {db_config.database} on {db_config.host}:{db_config.port}"
    )
    return database
