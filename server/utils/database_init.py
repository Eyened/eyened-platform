import os

from eyened_orm import (
    Creator,
    TaskState,
    Base,
    Database,
)
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..routes.auth import create_user
from eyened_orm.utils.config import EyenedORMConfig

def create_database():
    """
    Create database and tables if they don't exist.
    
    This function is safe for concurrent execution - multiple workers can call it
    simultaneously. The database and table creation operations use IF NOT EXISTS
    semantics to prevent conflicts.
    """
    # create generic engine for database creation
    dbstring = (
        f"mysql+pymysql://root:{settings.database_root_password}@{settings.database.host}:{settings.database.port}"
    )    
    temp_engine = create_engine(dbstring)

    # First check if database exists
    try:
        with temp_engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS {settings.database.database}"
                )
            )
            conn.commit()
    except Exception as e:
        raise RuntimeError(
            f"Could not check if database {settings.database.database} exists. Error: {str(e)}"
        )
    finally:
        temp_engine.dispose()
    
    # Now create tables using the correct database
    # Base.metadata.create_all() is safe for concurrent execution as it checks
    # for table existence before creating them
    print(settings)
    database = Database(settings)
    
    try:
        Base.metadata.create_all(database.engine)
        print(f"Created database: {settings.database.database}")
    except Exception as e:
        # If tables already exist (e.g., created by another worker), that's fine
        # Log the error but don't fail - the tables should exist
        print(f"Note: Table creation encountered an issue (may be due to concurrent initialization): {str(e)}")
        # Verify that the database connection works
        try:
            with database.get_session() as session:
                # Try a simple query to verify database is accessible
                session.execute(text("SELECT 1"))
        except Exception as verify_error:
            # If we can't even query, something is seriously wrong
            raise RuntimeError(
                f"Database tables may not be properly initialized. Error: {str(e)}. "
                f"Verification failed: {str(verify_error)}"
            ) from e

def init_admin(session: Session) -> None:
    """
    Initialize an admin user if ADMIN_USERNAME and ADMIN_PASSWORD are set in the config.
    
    This function is safe for concurrent execution - multiple workers can call it
    simultaneously without causing duplicate key errors.

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
    except IntegrityError as e:
        # Handle race condition: another worker may have created the admin user
        # between our check and the creation attempt
        session.rollback()
        # Verify the admin was created by another worker
        existing_admin = Creator.by_name(session, admin_username)
        if existing_admin:
            print(f"Admin user {admin_username} was created by another worker, skipping")
        else:
            # If it still doesn't exist, re-raise the error
            raise RuntimeError(f"Failed to create admin user due to database error: {str(e)}")
    except Exception as e:
        # Handle other exceptions (e.g., HTTPException from create_user if username exists)
        session.rollback()
        # Check again if admin exists (might have been created by another worker)
        existing_admin = Creator.by_name(session, admin_username)
        if existing_admin:
            print(f"Admin user {admin_username} already exists (created by another worker), skipping")
        else:
            raise RuntimeError(f"Failed to create admin user: {str(e)}")
   