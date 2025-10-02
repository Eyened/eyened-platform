from dataclasses import asdict
from typing import Optional
from pathlib import Path

import yaml
from eyened_orm.utils.config import EyenedORMConfig, env_field, configurable

# Ensure pathlib.Path objects are serialized as plain strings in YAML output
def _path_representer(dumper, data: Path):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))

yaml.SafeDumper.add_representer(Path, _path_representer)


@configurable
class Settings(EyenedORMConfig):
    # Server-specific settings
    admin_username: str = env_field("ADMIN_USERNAME", required=False, default="")
    admin_password: str = env_field("ADMIN_PASSWORD", required=False, default="")
    database_root_password: Optional[str] = env_field("DATABASE_ROOT_PASSWORD", required=False, default=None)

    # Print settings for debugging purposes - hide password and secret key
    def __str__(self):
        settings_dict = asdict(self)
        settings_dict["secret_key"] = "***HIDDEN***"
        settings_dict["admin_password"] = "***HIDDEN***"
        settings_dict["database"]["password"] = "***HIDDEN***"
        return yaml.safe_dump(settings_dict, default_flow_style=False, sort_keys=False)

    def __post_init__(self):
        """Handle database fallback logic after initialization."""
        if self.database.user == "" or self.database.password == "":
            self.database.user = "root"
            self.database.password = self.database_root_password

# load settings from environment variables
settings = Settings.create()
