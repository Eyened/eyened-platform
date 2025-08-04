from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from dotenv import load_dotenv
from eyened_orm.utils.config import DatabaseSettings, EyenedORMConfig
from eyened_orm.utils.zarr.manager import ZarrStorageManager
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import create_engine


def create_connection_string(config: DatabaseSettings):
    dbstring = (
        f"mysql+pymysql://{config.user}:{config.password}@{config.host}:{config.port}"
    )
    if config.database is not None:
        dbstring += f"/{config.database}"
    return dbstring


class EyenedSession(Session):
    """Custom session with built-in storage manager and config"""

    def __init__(self, config: EyenedORMConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        
    @property
    def storage_manager(self):
        if not hasattr(self, '_storage_manager'):
            self._storage_manager = ZarrStorageManager(self.config.segmentations_zarr_store)
        return self._storage_manager

class Database:
    """Database connection manager with built-in session and storage management"""

    def __init__(self, config: Optional[EyenedORMConfig | str | Path] = None):
        """
        config: EyenedORMConfig | Path | str
        if Path, load from .env file
        if None, initialize with default values (taken from environment variables)
        """
        if isinstance(config, (Path, str)):
            # load from .env file
            load_dotenv(dotenv_path=config)
            config = EyenedORMConfig()
        elif config is None:
            # initializes config with default values
            config = EyenedORMConfig()
        elif isinstance(config, EyenedORMConfig):
            pass
        else:
            raise ValueError(f"Invalid config type: {type(config)}")

        self.config = config

        conn_string = create_connection_string(self.config.database)

        print("creating engine with connection string", conn_string)
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
