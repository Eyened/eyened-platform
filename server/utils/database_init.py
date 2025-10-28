from eyened_orm import (
    Creator,
    Base,
    Database,
)
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from ..config import settings
from ..routes.auth import create_user


def create_database():
    # create generic engine for database creation
    dbstring = f"mysql+pymysql://root:{settings.database_root_password}@{settings.database.host}:{settings.database.port}"
    temp_engine = create_engine(dbstring)

    # First check if database exists
    try:
        with temp_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {settings.database.database}"))
    except Exception as e:
        raise RuntimeError(f"Could not check if database {settings.database.database} exists. Error: {str(e)}")

    # Now create tables using the correct database
    print(settings)
    database = Database(settings)

    Base.metadata.create_all(database.engine)


def init_admin(session: Session) -> None:
    """
    Initialize an admin user if ADMIN_USERNAME and ADMIN_PASSWORD are set in the config.

    Args:
        session: SQLAlchemy session to use for database operations
    """
    admin_username = settings.admin_username
    admin_password = settings.admin_password

    if admin_username is None or admin_password is None:
        raise ValueError("ADMIN_USERNAME and ADMIN_PASSWORD must be set in the config")

    # Check if admin already exists
    existing_admin = Creator.by_name(session, admin_username)

    if existing_admin:
        print("Admin user already exists, skipping creation")
        return

    try:
        create_user(
            session=session,
            username=admin_username,
            password=admin_password,
            description="Default admin user created during initialization",
        )
        print(f"Created admin user: {admin_username}")
    except Exception as e:
        raise RuntimeError(f"Failed to create admin user: {str(e)}")
