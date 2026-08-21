import logging
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from json import JSONDecodeError

import httpxyz
from eyened_orm.utils.pretty_settings import pretty_settings
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict, BaseSettings


@pretty_settings
class DbLogSettings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", env_prefix="EYENED_DBLOG_"
    )
    enabled: bool = Field(
        default=True,
        description="Emit audit events (AuditLog rows + eyened.audit stdout JSON).",
    )
    level: int = Field(
        default=logging.INFO,
        description="Level for the eyened.audit logger.",
    )


@pretty_settings
class RedisSettings(BaseSettings):
    """Broker for RQ job queues. Use a strong password if Redis is reachable off-host."""

    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", env_prefix="EYENED_REDIS_"
    )
    host: str = "redis"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None


@pretty_settings
class RqSettings(BaseSettings):
    """RQ worker / queue configuration."""

    model_config = SettingsConfigDict(frozen=True, extra="forbid", env_prefix="EYENED_RQ_")
    worker_queues: str = Field(
        default="default,cfi-roi,cfi-keypoints,cfi-odfd,cfi-quality",
        description=(
            "Comma-separated queue names for ``python -m server.rq_worker``. "
            "Must include ``default`` if this worker should process thumbnail jobs. "
            "Use ``cfi-roi`` only for the slim ROI worker."
        ),
    )


@pretty_settings
class OIDCSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="forbid", env_prefix="EYENED_OIDC_")

    client_id: str = Field(default="", description="The OIDC client ID")
    client_secret: SecretStr = Field(default="", description="The OIDC client secret")
    metadata_url: str = Field(default="", description="The full URL to the OIDC Provider metadata document, usually "
                                                      "found at `<issuer URL>/.well-known/openid-configuration`")
    redirect_url: str = Field(default="", description="The full URL to the redirect page in the EyeNED viewer where "
                                                      "the user is sent after authentication, should be "
                                                      "`https://<eyened URL>/users/oidc-callback`")
    provider_name: str = Field(default="OpenID Connect", description="The OIDC provider's name, or organisational name "
                                                                     "for the authentication flow")
    create_new_accounts: bool = Field(default=False, description="Whether or not to create new accounts for unknown "
                                                                 "users that authenticated through OIDC.")
    additional_token_validations: str = Field(default="", description="A key-value list of static token claims that "
                                                                      "must be available in received ID tokens, for "
                                                                      "example `iss=12345,tid=67890`. Keys and values "
                                                                      "are separated by `=`, key-value pairs by `,`.")


@dataclass(frozen=True)
class OIDCMetadata:
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


@lru_cache
def get_oidc_metadata(metadata_url: str) -> OIDCMetadata:
    """Fetch OIDC provider metadata and validate its required endpoints."""
    return validate_oidc_metadata(_fetch_oidc_metadata(metadata_url))


def _fetch_oidc_metadata(metadata_url: str) -> dict:
    """Fetch OIDC provider metadata from the provider's well-known URL."""
    with httpxyz.Client() as client:
        response = client.get(metadata_url)

    if response.status_code != httpxyz.codes.OK:
        raise ValueError(
            f"OIDC metadata URL '{metadata_url}' seems to be invalid, "
            f"HTTP status code returned: {response.status_code}"
        )

    try:
        metadata = response.json()
    except JSONDecodeError:
        raise ValueError("OIDC metadata URL returned unparsable JSON data")

    return metadata


def validate_oidc_metadata(metadata: dict) -> OIDCMetadata:
    """Validate the OIDC metadata fields used by the authentication flow."""
    for key in ["authorization_endpoint", "token_endpoint", "jwks_uri"]:
        if key not in metadata:
            raise ValueError(f"OIDC metadata URL response is missing required key '{key}'")

    return OIDCMetadata(
        authorization_endpoint=metadata["authorization_endpoint"],
        token_endpoint=metadata["token_endpoint"],
        jwks_uri=metadata["jwks_uri"],
    )


@pretty_settings
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", env_prefix="EYENED_API_"
    )
    debug: bool = False
    public_auth_disabled: bool = False
    # Names the account the dev-auth bypass logs in as, and the account
    # `eorm init-admin` bootstraps. Two places naming the same account that
    # disagree is the failure dev/sample.env's note exists to prevent. The
    # account's password is not configured here: the dev bypass never posts
    # credentials, so the server has no use for it. `eorm init-admin` reads
    # it directly from EYENED_API_ADMIN_PASSWORD instead.
    admin_username: str = Field(default="admin", min_length=1)
    auth_password_enabled: bool = True
    auth_oidc_enabled: bool = False
    secret_key: SecretStr = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    jwt_cookie_name: str = "jwt_token"
    refresh_cookie_name: str = "refresh_token"
    gzip_minimum_size: int = 1024 * 1024

    # Thread capacity is the binding constraint and the pool is sized to serve
    # it, so a request never waits on pool checkout. anyio's own default is 40
    # threads, which against SQLAlchemy's default 5+10 pool would queue 25 of
    # them behind a 30s pool_timeout.
    threadpool_limit: int = Field(
        default=16,
        ge=1,
        description="Threads this API worker runs sync handlers in.",
    )
    pool_size: int = Field(
        default=16,
        ge=1,
        description="Persistent DB connections per API worker.",
    )
    max_overflow: int = Field(
        default=4,
        ge=0,
        description="Extra burst connections above pool_size, for dependency-time checkouts.",
    )

    @model_validator(mode="after")
    def _threads_cannot_outnumber_connections(self) -> "Settings":
        capacity = self.pool_size + self.max_overflow
        if self.threadpool_limit > capacity:
            raise ValueError(
                f"threadpool_limit ({self.threadpool_limit}) exceeds pool capacity "
                f"({self.pool_size} + {self.max_overflow} = {capacity}). The excess "
                "threads would block in pool.connect() until pool_timeout. Raise "
                "pool_size/max_overflow or lower threadpool_limit."
            )
        return self

    default_study_date: date = date(1970, 1, 1)

    redis: RedisSettings = Field(default_factory=RedisSettings)
    rq: RqSettings = Field(default_factory=RqSettings)
    db_log: DbLogSettings = Field(default_factory=DbLogSettings)
    oidc: OIDCSettings = Field(default_factory=OIDCSettings)

    zarr_store: str = "/storage/segmentations.zarr"

    @property
    def secret_key_value(self) -> str:
        return str(self.secret_key.get_secret_value())


settings = Settings()


def get_redis_connection():
    """Redis client for RQ (same connection used for enqueue and job status)."""
    from redis import Redis

    rs = settings.redis
    kwargs: dict = {"host": rs.host, "port": rs.port, "db": rs.db}
    if rs.password is not None:
        pw = rs.password.get_secret_value()
        if pw:
            kwargs["password"] = pw
    return Redis(**kwargs)


def get_redis_url() -> str:
    """Redis URL for ``rq worker --url`` on a machine with the same env as the API."""
    from urllib.parse import quote

    rs = settings.redis
    if rs.password is not None:
        pw = rs.password.get_secret_value()
        if pw:
            enc = quote(pw, safe="")
            return f"redis://:{enc}@{rs.host}:{rs.port}/{rs.db}"
    return f"redis://{rs.host}:{rs.port}/{rs.db}"
