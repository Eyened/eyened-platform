import logging
from datetime import date
from pathlib import Path
from eyened_orm.utils.pretty_settings import pretty_settings
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict, BaseSettings


@pretty_settings
class DbLogSettings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", env_prefix="EYENED_DBLOG_"
    )
    file_path: Path | None = Field(
        default=None,
        description=(
            "Optional output path for DB modification logs. "
            "Set EYENED_DBLOG_FILE_PATH to enable file logging; "
            "if omitted, DB logging is disabled."
        ),
    )
    level: int = Field(
        default=logging.INFO,
        description="Log level used when DB logging is enabled.",
    )
    max_bytes: int = Field(
        default=10 * 1024 * 1024,
        description="Maximum log file size before rotation when enabled.",
    )
    backup_count: int = Field(
        default=5,
        description="Number of rotated DB log files to keep when enabled.",
    )


@pretty_settings
class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", env_prefix="EYENED_REDIS_"
    )
    host: str = "redis"
    port: int = 6379


@pretty_settings
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", env_prefix="EYENED_API_"
    )
    debug: bool = False
    public_auth_disabled: bool = False
    secret_key: SecretStr = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    jwt_cookie_name: str = "jwt_token"
    refresh_cookie_name: str = "refresh_token"
    gzip_minimum_size: int = 1024 * 1024

    default_study_date: date = date(1970, 1, 1)

    redis: RedisSettings = Field(default_factory=RedisSettings)
    db_log: DbLogSettings = Field(default_factory=DbLogSettings)

    zarr_store: str = "/storage/segmentations.zarr"

    @property
    def secret_key_value(self) -> str:
        return str(self.secret_key.get_secret_value())


settings = Settings()
