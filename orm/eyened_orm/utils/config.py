import os
from datetime import date
from pathlib import Path, PurePath
from typing import Any, Dict, Literal, Optional

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    user: str
    password: str
    host: str
    database: str
    port: int
    raise_on_warnings: bool = True


yaml.SafeDumper.add_multi_representer(
    PurePath, lambda d, data: d.represent_scalar("tag:yaml.org,2002:str", str(data))
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="forbid")

    database: DatabaseSettings
    secret_key: str
    images_basepath: Path
    segmentations_zarr_store: Path
    thumbnails_path: Path
    annotations_path: Path
    default_study_date: Optional[date]
    cfi_cache_path: Optional[Path]
    image_server_url: Optional[str]
    public_auth_disabled: bool
    environment: str
    db_log_file_path: str
    db_log_level: int
    db_log_max_bytes: int
    db_log_backup_count: int
    redis_host: str
    redis_port: int

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (init_settings,)

    def __str__(self):
        d = self.model_dump()
        d["secret_key"] = "***HIDDEN***"
        d["database"]["password"] = "***HIDDEN***"
        return yaml.safe_dump(d, default_flow_style=False, sort_keys=False)


def _load(path: Path, required: bool = True) -> Dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Config file not found: {path}")
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a YAML mapping: {path}")
    return data


def _merge(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for d in dicts:
        for k, v in d.items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = _merge(out[k], v)
            else:
                out[k] = v
    return out


def load_settings(env: str) -> Settings:
    config_dir = Path(os.getenv("EYENED_CONFIG_DIR"))
    base = _load(config_dir / "config.base.yaml")
    local = _load(config_dir / "config.local.yaml", required=False)
    env_cfg = _load(config_dir / f"config.{env}.yaml")
    combined = _merge(base, env_cfg, local)
    user = combined["database"]["user"]
    secrets = {
        "database": {
            "password": os.getenv(f"EYENED_DATABASE_PASSWORD_{user.upper()}", ""),
        },
        "secret_key": os.getenv("EYENED_SECRET_KEY", ""),
    }

    return Settings.model_validate(_merge(combined, secrets))
