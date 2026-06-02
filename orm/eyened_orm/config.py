from functools import lru_cache
from os import PathLike
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .utils.pretty_settings import pretty_settings


@pretty_settings
class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True, extra="ignore", env_prefix="EYENED_DATABASE_"
    )

    user: str
    password: SecretStr
    host: str = "database"
    database: str = "eyened_database"
    port: int = 3306
    raise_on_warnings: bool = True


@pretty_settings
class APISettings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True, extra="ignore", env_prefix="EYENED_API_"
    )
    url: str
    username: str
    password: SecretStr


EnvFile = str | PathLike[str] | None


@lru_cache
def load_database_settings(env_file: EnvFile = None) -> DatabaseSettings:
    """Load database settings from the environment or a specific .env file."""
    if env_file is None:
        return DatabaseSettings()

    env_path = Path(env_file).expanduser()
    return DatabaseSettings(_env_file=str(env_path))


@lru_cache
def load_api_settings() -> APISettings:
    return APISettings()
