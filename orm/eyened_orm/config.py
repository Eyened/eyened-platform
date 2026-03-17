from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .utils.pretty_settings import pretty_settings


@pretty_settings
class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", env_prefix="EYENED_DATABASE_"
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
        frozen=True, extra="forbid", env_prefix="EYENED_API_"
    )
    url: str
    username: str
    password: SecretStr

@lru_cache
def load_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache
def load_api_settings() -> APISettings:
    return APISettings()
