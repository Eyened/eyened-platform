from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .base import Base

def create_connection_string_mysql(user, password, host, port, database=None, **kwargs):
    if database is None:
        return f"mysql+pymysql://{user}:{password}@{host}:{port}"
    else:
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

class DBManager:
    _engine = None
    _SessionLocal = None

    @classmethod
    def init(cls, config: str | dict):
        """Initialize the database session factory with the given config."""
        
        if type(config) == str:
            from eyened_orm.utils.config import get_config
            config = get_config(config)
        
        conn_string = create_connection_string_mysql(**config["database"])
        if cls._engine is None:
            cls._engine = create_engine(conn_string, pool_pre_ping=True)
            cls._SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=cls._engine
            )

        Base.config = config

    @classmethod
    @contextmanager
    def yield_session(cls):
        """Context manager for session management."""
        if cls._SessionLocal is None:
            raise RuntimeError(
                "DBManager is not initialized. Call DBManager.init(config) first."
            )

        session = cls._SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @classmethod
    def get_session(cls):
        """Returns a new session for manual control (useful for interactive shells)."""
        if cls._SessionLocal is None:
            raise RuntimeError(
                "DBManager is not initialized. Call DBManager.init(config) first."
            )
        session = cls._SessionLocal()  # User is responsible for closing it
        return session

    @classmethod
    def get_engine(cls):
        """Returns the engine instance."""
        if cls._engine is None:
            raise RuntimeError(
                "DBManager is not initialized. Call DBManager.init(config) first."
            )
        return cls._engine
