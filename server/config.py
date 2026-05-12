import logging
from datetime import date
from anyio.functools import lru_cache
from json import JSONDecodeError
from pathlib import Path

import httpxyz
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
class OIDCSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="forbid", env_prefix="EYENED_OIDC_")
    client_id: str = ""
    client_secret: SecretStr = ""
    connect_url: str = ""
    redirect_url: str = ""
    provider_name: str = "OpenID Connect"

    @property
    def client_secret_value(self) -> str:
        return str(self.client_secret.get_secret_value())

    @lru_cache
    async def _get_config_data(self):
        """Get OIDC configuration data from connect URL and validate it"""
        async with httpxyz.AsyncClient() as client:
            response = await client.get(self.connect_url)

        if response.status_code != httpxyz.codes.OK:
            raise ValueError(f"OIDC connect URL '{self.connect_url}' seems to be invalid, HTTP status code returned: {response.status_code}")

        try:
            config = response.json()
        except JSONDecodeError:
            raise ValueError("OIDC connect URL returned unparsable JSON data")

        for key in ["authorization_endpoint", "token_endpoint"]:
            if key not in config:
                raise ValueError(f"OIDC connect URL response is missing required key '{key}'")

        return config

    async def get_authorize_url(self) -> str:
        config = await self._get_config_data()
        return config["authorization_endpoint"]


@pretty_settings
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", env_prefix="EYENED_API_"
    )
    debug: bool = False
    public_auth_disabled: bool = False
    auth_password_enabled: bool = True
    auth_oidc_enabled: bool = False
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
    oidc: OIDCSettings = Field(default_factory=OIDCSettings)

    zarr_store: str = "/storage/segmentations.zarr"

    @property
    def secret_key_value(self) -> str:
        return str(self.secret_key.get_secret_value())


settings = Settings()
