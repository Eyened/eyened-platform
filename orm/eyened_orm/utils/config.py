from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional, Union, Mapping, Any
from pathlib import Path
import os


@dataclass
class DatabaseSettings:
    user: str
    password: str
    host: str
    database: str
    port: int
    raise_on_warnings: bool = True


@dataclass
class EyenedORMConfig:
    database: DatabaseSettings
    secret_key: str
    images_basepath: Path
    segmentations_zarr_store: Path
    thumbnails_path: Path
    annotations_path: Path
    default_study_date: Optional[date]
    image_server_url: Optional[str]


def _parse_int(value):
    return int(value) if value is not None else None


def _parse_bool(value):
    if value is None:
        return None
    return str(value).lower() in ("true", "1", "yes", "on")


def _parse_path(value):
    return Path(value) if value is not None else None


def _parse_date(value):
    return date.fromisoformat(value) if value is not None else None


def load_config_dict_from_env(env: Mapping[str, str]) -> dict:
    """Convert environment variables to a config dict structure."""
    
    def get_env(key: str, required: bool = True, default=None):
        value = env.get(key)
        if required and value is None:
            raise ValueError(f"Missing required environment variable: {key}")
        return value if value is not None else default
    
    return {
        "database": {
            "user": get_env("DATABASE_USER"),
            "password": get_env("DATABASE_PASSWORD"),
            "host": get_env("DATABASE_HOST"),
            "database": get_env("DATABASE_NAME"),
            "port": _parse_int(get_env("DATABASE_PORT")),
            "raise_on_warnings": _parse_bool(get_env("DATABASE_RAISE_ON_WARNINGS", required=False, default="true")),
        },
        "secret_key": get_env("SECRET_KEY"),
        "images_basepath": _parse_path(get_env("IMAGES_BASEPATH", required=False, default="/images")),
        "segmentations_zarr_store": _parse_path(get_env("SEGMENTATIONS_ZARR_STORE", required=False, default="/storage/segmentations.zarr")),
        "thumbnails_path": _parse_path(get_env("THUMBNAILS_PATH", required=False, default="/storage/thumbnails")),
        "annotations_path": _parse_path(get_env("ANNOTATIONS_PATH", required=False, default="/storage/annotations")),
        "default_study_date": _parse_date(get_env("DEFAULT_STUDY_DATE", required=False, default="1970-01-01")),
        "image_server_url": get_env("IMAGE_SERVER_URL", required=False),
    }


def load_config(source: Optional[Union[str, Path, Mapping[str, Any], dict]] = None) -> EyenedORMConfig:
    """
    Load EyenedORMConfig from various sources.
    
    Args:
        source: Can be:
            - None: Load from os.environ
            - str/Path: Load from .env file
            - Mapping (e.g. os.environ): Flat environment variables dict
            - dict: Nested config dict (e.g. from YAML)
    
    Returns:
        EyenedORMConfig instance
    """
    if source is None:
        config_dict = load_config_dict_from_env(os.environ)
    elif isinstance(source, (str, Path)):
        from dotenv import dotenv_values
        env_path = Path(source)
        if not env_path.exists():
            raise FileNotFoundError(f"Environment file not found: {env_path}")
        env = {k: v for k, v in dotenv_values(dotenv_path=env_path).items() if v is not None}
        config_dict = load_config_dict_from_env(env)
    elif isinstance(source, (Mapping, dict)):
        # Check if it's already a nested config dict (has 'database' key with nested dict)
        if 'database' in source and isinstance(source.get('database'), dict):
            config_dict = source  # Already structured as nested dict
        else:
            config_dict = load_config_dict_from_env(source)  # Flat env vars
    else:
        raise ValueError(f"Invalid source type: {type(source)}")
    
    return EyenedORMConfig(
        database=DatabaseSettings(**config_dict["database"]),
        **{k: v for k, v in config_dict.items() if k != "database"}
    )
