from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .base import Base


class DBManager:
    _engine = None
    _SessionLocal = None

    @classmethod
    def init(cls, config: str | dict, create_all=False):
        """Initialize the database session factory with the given config."""
        
        if type(config) == str:
            from eyened_orm.utils.config import get_config
            config = get_config(config)
        
        if cls._engine is None:
            db = config["database"]

            if "conn_string" in db:
                conn_string = db["conn_string"]
            else:
                conn_string = (
                    f"mysql+pymysql://{db['user']}:{db['password']}"
                    f"@{db['host']}:{db['port']}/{db['database']}"
                )

            cls._engine = create_engine(conn_string, pool_pre_ping=True)
            cls._SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=cls._engine
            )

            if create_all:
                Base.metadata.create_all(cls._engine)
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
