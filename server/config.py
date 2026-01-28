from dataclasses import asdict, dataclass
from typing import Literal, Optional
from pathlib import Path, PurePath
import os

import yaml
from eyened_orm.utils.config import EyenedORMConfig, load_config

# Ensure pathlib.Path objects are serialized as plain strings in YAML output
def _path_representer(dumper, data: PurePath):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))

yaml.SafeDumper.add_multi_representer(PurePath, _path_representer)


@dataclass
class Settings(EyenedORMConfig):
    admin_username: str = ""
    admin_password: str = ""
    database_root_password: Optional[str] = None
    public_auth_disabled: bool = False
    environment: Literal['development', 'production'] = 'production'
    db_log_file_path: str = "/var/log/eyened/db_modifications.log"
    db_log_level: int = 20  # logging.INFO
    db_log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    db_log_backup_count: int = 5

    def __str__(self):
        settings_dict = asdict(self)
        settings_dict["secret_key"] = "***HIDDEN***"
        settings_dict["admin_password"] = "***HIDDEN***"
        settings_dict["database"]["password"] = "***HIDDEN***"
        return yaml.safe_dump(settings_dict, default_flow_style=False, sort_keys=False)


def load_settings(env_file: Optional[str | Path] = None) -> Settings:
    """
    Load settings from environment variables or .env file.
    
    Args:
        env_file: Optional path to .env file. If None, loads from current environment.
    
    Returns:
        Settings object with all configuration loaded
    """
    base_config = load_config(env_file)
    
    settings = Settings(
        database=base_config.database,
        secret_key=base_config.secret_key,
        images_basepath=base_config.images_basepath,
        segmentations_zarr_store=base_config.segmentations_zarr_store,
        thumbnails_path=base_config.thumbnails_path,
        annotations_path=base_config.annotations_path,
        default_study_date=base_config.default_study_date,
        image_server_url=base_config.image_server_url,
        admin_username=os.getenv("ADMIN_USERNAME", ""),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        database_root_password=os.getenv("DATABASE_ROOT_PASSWORD"),
        environment=os.getenv("EYENED_ENV", "production"),
        public_auth_disabled=os.getenv("VITE_PUBLIC_AUTH_DISABLED", "0") == "1",
        db_log_file_path=os.getenv("DB_LOG_FILE_PATH", "/var/log/eyened/db_modifications.log"),
        db_log_level=int(os.getenv("DB_LOG_LEVEL", "20")),  # logging.INFO
        db_log_max_bytes=int(os.getenv("DB_LOG_MAX_BYTES", str(10 * 1024 * 1024))),  # 10MB
        db_log_backup_count=int(os.getenv("DB_LOG_BACKUP_COUNT", "5")),
    )
    
    # Handle database fallback logic
    if settings.database.user == "" or settings.database.password == "":
        settings.database.user = "root"
        settings.database.password = settings.database_root_password
    
    return settings
    
# load settings from environment variables
settings = load_settings()
