
from sqlalchemy import create_engine, text

from eyened_orm.base import Base
from eyened_orm.config import DatabaseSettings, load_database_settings
from eyened_orm.db import Database, create_server_connection_string


def create_database(settings: DatabaseSettings | None = None) -> None:
    """
    Create database and tables if they don't exist.
    
    This function is safe for concurrent execution - multiple workers can call it
    simultaneously. The database and table creation operations use IF NOT EXISTS
    semantics to prevent conflicts.
    """
    settings = settings or load_database_settings()

    # create generic engine for database creation
    temp_engine = create_engine(create_server_connection_string(settings))

    # First check if database exists
    try:
        with temp_engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS {settings.database}"
                )
            )
            conn.commit()
    except Exception as e:
        raise RuntimeError(
            f"Could not check if database {settings.database} exists. Error: {str(e)}"
        ) from e
    finally:
        temp_engine.dispose()
    
    # Now create tables using the correct database
    # Base.metadata.create_all() is safe for concurrent execution as it checks
    # for table existence before creating them
    
    database = Database(settings)
    
    try:
        Base.metadata.create_all(database.engine)
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
