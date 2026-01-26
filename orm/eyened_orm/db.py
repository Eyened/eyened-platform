from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Mapping, Optional

from eyened_orm.utils.config import Settings, load_settings
from eyened_orm.utils.zarr.manager import ZarrStorageManager
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine


def create_connection_string(database):
    return f"mysql+pymysql://{database.user}:{database.password}@{database.host}:{database.port}/{database.database}"


class EyenedSession(Session):
    """Custom session with built-in storage manager and config"""

    def __init__(self, config: Settings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config

    @property
    def storage_manager(self):
        if not hasattr(self, "_storage_manager"):
            self._storage_manager = ZarrStorageManager(
                self.config.segmentations_zarr_store
            )
        return self._storage_manager


class Database:
    """Database connection manager with built-in session and storage management"""

    def __init__(self, *, config: Settings | None = None, env: str | None = None):
        if config is not None:
            self.config = config
        elif env is not None:
            self.config = load_settings(env)
        else:
            raise ValueError("Provide either config or env")

        conn_string = create_connection_string(self.config.database)

        # print("creating engine with connection string", conn_string)
        self.engine = create_engine(conn_string, pool_pre_ping=True)

        # Create session factory with custom session class
        self._session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine, class_=EyenedSession
        )

    @contextmanager
    def get_session(self) -> Generator[EyenedSession, None, None]:
        session: EyenedSession = self._session_factory(config=self.config)
        try:
            yield session
        finally:
            session.close()

    def create_session(self) -> EyenedSession:
        """
        For manual session management.
        User is responsible for closing the session.
        """
        return self._session_factory(config=self.config)
