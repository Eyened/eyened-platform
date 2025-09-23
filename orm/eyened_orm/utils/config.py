from dataclasses import dataclass
from datetime import date
from typing import Optional, Mapping
from pathlib import Path


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
    secret_key: str = ""
    images_basepath: str = "/images"
    segmentations_zarr_store: str = "/storage/segmentations.zarr"
    thumbnails_path: str = "/storage/thumbnails"
    annotations_path: str = "/storage/annotations"
    default_study_date: Optional[date] = date(1970, 1, 1)
    cfi_cache_path: Optional[str] = None
    image_server_url: Optional[str] = None


def _require(env: Mapping[str, str], key: str) -> str:
    if key not in env or env[key] in (None, ""):
        raise ValueError(f"Missing required environment key: {key}")
    return env[key]


def load_config_from_environ(env: Mapping[str, str]) -> EyenedORMConfig:
    db_user = _require(env, "DATABASE_USER")
    db_password = _require(env, "DATABASE_PASSWORD")
    db_host = _require(env, "DATABASE_HOST")
    db_name = _require(env, "DATABASE_NAME")
    db_port_raw = _require(env, "DATABASE_PORT")
    secret_key = _require(env, "SECRET_KEY")

    try:
        db_port = int(db_port_raw)
    except ValueError:
        raise ValueError(f"DATABASE_PORT must be an integer, got: {db_port_raw}")

    database = DatabaseSettings(
        user=db_user,
        password=db_password,
        host=db_host,
        database=db_name,
        port=db_port,
    )

    images_basepath = env.get("IMAGES_BASEPATH", "/images")
    segmentations_zarr_store = env.get("SEGMENTATIONS_ZARR_STORE", "/storage/segmentations.zarr")
    thumbnails_path = env.get("THUMBNAILS_PATH", "/storage/thumbnails")
    annotations_path = env.get("ANNOTATIONS_PATH", "/storage/annotations")

    default_study_date_raw = env.get("DEFAULT_STUDY_DATE")
    if default_study_date_raw:
        try:
            default_study_date = date.fromisoformat(default_study_date_raw)
        except ValueError:
            raise ValueError(
                f"DEFAULT_STUDY_DATE must be YYYY-MM-DD, got: {default_study_date_raw}"
            )
    else:
        default_study_date = date(1970, 1, 1)

    cfi_cache_path = env.get("CFI_CACHE_PATH")
    image_server_url = env.get("IMAGE_SERVER_URL")

    return EyenedORMConfig(
        database=database,
        secret_key=secret_key,
        images_basepath=images_basepath,
        segmentations_zarr_store=segmentations_zarr_store,
        thumbnails_path=thumbnails_path,
        annotations_path=annotations_path,
        default_study_date=default_study_date,
        cfi_cache_path=cfi_cache_path,
        image_server_url=image_server_url,
    )


def load_config_from_env_file(path: str | Path) -> EyenedORMConfig:
    from dotenv import dotenv_values

    values = dotenv_values(dotenv_path=Path(path))
    # dotenv_values returns dict[str, str|None]; filter out None
    filtered = {k: v for k, v in values.items() if v is not None}
    return load_config_from_environ(filtered)
