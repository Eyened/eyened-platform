from dataclasses import asdict
from typing import Optional
import os
from dataclasses import asdict, dataclass
from typing import Literal, Optional
from pathlib import Path, PurePath

import yaml
from eyened_orm.utils.config import EyenedORMConfig, env_field, configurable

# Ensure pathlib.Path objects are serialized as plain strings in YAML output
def _path_representer(dumper, data: PurePath):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))

yaml.SafeDumper.add_multi_representer(PurePath, _path_representer)


@configurable
class Settings(EyenedORMConfig):
    # Server-specific settings
    admin_username: str = env_field("ADMIN_USERNAME", required=False, default="")
    admin_password: str = env_field("ADMIN_PASSWORD", required=False, default="")
    database_root_password: Optional[str] = env_field("DATABASE_ROOT_PASSWORD", required=False, default=None)
    
    # Authentication bypass for development (reads from PUBLIC_AUTH_DISABLED env var)
    public_auth_disabled: bool = env_field("VITE_PUBLIC_AUTH_DISABLED", required=False, default=True)
    environment: Literal['development', 'production'] = env_field("EYENED_ENV", required=False, default="production")

    # Print settings for debugging purposes - hide password and secret key
    def __str__(self):
        settings_dict = asdict(self)
        settings_dict["secret_key"] = "***HIDDEN***"
        settings_dict["admin_password"] = "***HIDDEN***"
        settings_dict["database"]["password"] = "***HIDDEN***"
        return yaml.safe_dump(settings_dict, default_flow_style=False, sort_keys=False)
        return yaml.dump(settings_dict, default_flow_style=False)


def load_settings(env_file: Optional[str | Path] = None) -> Settings:
    """
    Load settings from environment variables or .env file.
    
    Args:
        env_file: Optional path to .env file. If None, loads from current environment.
    
    Returns:
        Settings object with all configuration loaded
    """
    if env_file:
        # Load from .env file
        base_config = load_config_from_env_file(env_file)
    else:
        # Load from current environment
        base_config = load_config_from_environ(os.environ)
    
    # Create Settings object by copying the base config and adding server-specific settings
    settings = Settings(
        database=base_config.database, 
        secret_key=base_config.secret_key,
        images_basepath=base_config.images_basepath,
        segmentations_zarr_store=base_config.segmentations_zarr_store,
        thumbnails_path=base_config.thumbnails_path,
        annotations_path=base_config.annotations_path,
        default_study_date=base_config.default_study_date,
        cfi_cache_path=base_config.cfi_cache_path,
        image_server_url=base_config.image_server_url,
        # Server-specific settings
        admin_username=os.getenv("ADMIN_USERNAME", ""),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        database_root_password=os.getenv("DATABASE_ROOT_PASSWORD"),
        environment=os.getenv("EYENED_ENV", "production"),
        public_auth_disabled=os.getenv("VITE_PUBLIC_AUTH_DISABLED", "1") == "1",
    )
    
    # Handle database fallback logic
    if settings.database.user == "" or settings.database.password == "":
        settings.database.user = "root"
        settings.database.password = settings.database_root_password
    
    return settings

    def __post_init__(self):
        """Handle database fallback logic after initialization."""
        if self.database.user == "" or self.database.password == "":
            self.database.user = "root"
            self.database.password = self.database_root_password

# load settings from environment variables
settings = Settings.create()
