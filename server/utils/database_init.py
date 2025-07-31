import os

from eyened_orm import (
    Creator,
    TaskState,
    Base,
    Database,
)
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlmodel import create_engine

from ..config import settings
from ..routes.auth import create_user
from eyened_orm.utils.config import EyenedORMConfig

def create_database():
    # create generic engine for database creation
    root_password = os.environ.get("DATABASE_ROOT_PASSWORD")
    dbstring = (
        f"mysql+pymysql://root:{root_password}@{settings.database.host}:{settings.database.port}"
    )    
    temp_engine = create_engine(dbstring)

    # First check if database exists
    try:
        with temp_engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{settings.database.database}'"
                )
            )
            if not result.fetchone():
                # Database doesn't exist, try to create it
                try:
                    conn.execute(
                        text(
                            f"CREATE DATABASE IF NOT EXISTS {settings.database.database}"
                        )
                    )
                except Exception as e:
                    raise RuntimeError(
                        f"Database {settings.database.database} does not exist and could not be created. Error: {str(e)}"
                    )
    except Exception as e:
        raise RuntimeError(
            f"Could not check if database {settings.database.database} exists. Error: {str(e)}"
        )

    # Create user if it doesn't exist
    try:
        create_database_user(temp_engine)
    except Exception as e:
        raise RuntimeError(
            f"Could not create database user for {settings.database.database}. Error: {str(e)}"
        )
    
    # Now create tables using the correct database
    print(settings)
    database = Database(EyenedORMConfig(database=settings.database))
    
    Base.metadata.create_all(database.engine)


def create_database_user(engine):
    """
    Creates a database user with INSERT, UPDATE, DELETE privileges if it doesn't exist.
    Uses credentials from settings.database.
    """
    db_user = settings.database.user
    db_password = settings.database.password
    db_database = settings.database.database

    try:
        with engine.connect() as conn:
            # Check if user exists
            result = conn.execute(
                text(f"SELECT User FROM mysql.user WHERE User = '{db_user}'")
            )
            if result.fetchone():
                print(f"Database user {db_user} already exists")
            else:
                # Create user if it doesn't exist
                try:
                    conn.execute(
                        text(
                            f"CREATE USER '{db_user}'@'%' IDENTIFIED BY '{db_password}'"
                        )
                    )
                    print(f"Created database user: {db_user}")
                except Exception as e:
                    raise RuntimeError(
                        f"Could not create database user {db_user}. Error: {str(e)}"
                    )

            # Grant limited privileges to user
            try:
                conn.execute(
                    text(
                        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {db_database}.* TO '{db_user}'@'%'"
                    )
                )
                conn.execute(text("FLUSH PRIVILEGES"))
                print(
                    f"Granted SELECT, INSERT, UPDATE, DELETE privileges to user {db_user} on database {db_database}"
                )
            except Exception as e:
                raise RuntimeError(
                    f"Could not grant privileges to user {db_user}. Error: {str(e)}"
                )

    except Exception as e:
        raise RuntimeError(f"Could not manage database user {db_user}. Error: {str(e)}")


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
   

def init_task_states(session: Session):
    expected_states = [
        "Not started",
        "Busy",
        "Ready",
    ]

    task_states = TaskState.fetch_all(session)
    for name in expected_states:
        if name not in [t.TaskStateName for t in task_states]:
            task_state = TaskState(TaskStateName=name)
            print(f"Adding task state: {task_state}")
            session.add(task_state)

    session.commit()
