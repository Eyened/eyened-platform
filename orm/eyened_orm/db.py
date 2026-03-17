from contextlib import contextmanager
from typing import Generator

from eyened_orm.config import DatabaseSettings, load_database_settings
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import Engine, create_engine


def create_connection_string(settings: DatabaseSettings) -> str:
    pw = settings.password.get_secret_value()
    return f"mysql+pymysql://{settings.user}:{pw}@{settings.host}:{settings.port}/{settings.database}"


def create_server_connection_string(settings: DatabaseSettings) -> str:
    pw = settings.password.get_secret_value()
    return f"mysql+pymysql://{settings.user}:{pw}@{settings.host}:{settings.port}"


class EyenedSession(Session):
    def __init__(
        self,
        *args,
        database_settings: DatabaseSettings | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.database_settings = database_settings


class Database:
    """Database connection manager with built-in session and storage management"""

    database_settings: DatabaseSettings
    engine: Engine
    _session_factory: sessionmaker

    def __init__(
        self,
        database_settings: DatabaseSettings | None = None,
    ):
        self.database_settings = database_settings or load_database_settings()

        self.engine = create_engine(
            create_connection_string(self.database_settings), pool_pre_ping=True
        )
        self._session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            class_=EyenedSession,
        )

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session: Session = self._session_factory(
            database_settings=self.database_settings
        )
        try:
            yield session
        finally:
            session.close()

    def create_session(self) -> Session:
        """
        For manual session management.
        User is responsible for closing the session.
        """
        return self._session_factory(database_settings=self.database_settings)
