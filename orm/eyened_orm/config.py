from functools import lru_cache
from pathlib import Path
import os
import re
from typing import Dict
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


@lru_cache
def load_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache
def load_routing_settings() -> Dict[str, str]:
    """
    Parse nginx.conf and return {alias_name: alias_path}.
    """
    config_path = os.environ.get("EYENED_ROUTING_CONFIG")
    if config_path:
        path = Path(config_path).expanduser()
    else:
        return {}

    content = path.read_text()

    aliases: Dict[str, str] = {}
    current_location: str | None = None

    location_re = re.compile(r"^location\s+([^\s{]+)\s*\{")
    alias_re = re.compile(r"^alias\s+([^;]+);")

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        location_match = location_re.match(stripped)
        if location_match:
            current_location = location_match.group(1)
            continue

        if stripped.startswith("}"):
            current_location = None
            continue

        if current_location:
            alias_match = alias_re.match(stripped)
            if alias_match:
                key = current_location.strip("/")
                if key:
                    aliases[key] = alias_match.group(1).strip().rstrip("/")

    return aliases
