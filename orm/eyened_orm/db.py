from contextlib import contextmanager

from eyened_orm.utils.config import EyenedORMConfig, DatabaseSettings

from sqlmodel import create_engine
from sqlalchemy.orm import sessionmaker

from .base import Base

def create_connection_string(config: DatabaseSettings):
    dbstring = f"mysql+pymysql://{config.user}:{config.password}@{config.host}:{config.port}"
    if config.database is not None:
        dbstring += f"/{config.database}"
    return dbstring

class DBManager:
    _engine = None
    _SessionLocal = None
    _config = None
    @classmethod
    def init(cls, config: None | str | EyenedORMConfig = None):
        """Initialize the database session factory with the given config."""
        if config is None or isinstance(config, str):
            from eyened_orm.utils.config import get_config
            cls._config = get_config(config)

        conn_string = create_connection_string(cls._config.database)
        if cls._engine is None:
            cls._engine = create_engine(conn_string, pool_pre_ping=True)
            cls._SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=cls._engine
            )

        

    @classmethod
    @contextmanager
    def yield_session(cls):
        """Context manager for session management."""
        if cls._SessionLocal is None:
            print("DBManager not initialized, using default config ('.env')")
            cls.init()

        session = cls._SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @classmethod
    def get_session(cls):
        """Returns a new session for manual control (useful for interactive shells)."""
        if cls._SessionLocal is None:
            print("DBManager not initialized, using default config ('.env')")
            cls.init()
        session = cls._SessionLocal()  # User is responsible for closing it
        return session

    @classmethod
    def get_engine(cls):
        """Returns the engine instance."""
        if cls._engine is None:
            print("DBManager not initialized, using default config ('.env')")
            cls.init()
        return cls._engine
