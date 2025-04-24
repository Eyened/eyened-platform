from typing import Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # IMPORTANT: the base fields in this file must match environment variable names exactly (with the exception of case)
    # Base settings takes care of reading the environment internally
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    viewer_env: str = "production"

    # Authentication
    jwt_secret_key: str
    access_token_duration: int = Field(
        validation_alias="PUBLIC_AUTH_TOKEN_DURATION",
        default=259200,  # 3 days in seconds
    )
    refresh_token_duration: int = Field(
        validation_alias="AUTH_REFRESH_TOKEN_DURATION",
        default=2592000,  # 30 days in seconds
    )

    # Default username and password for the admin user
    admin_username: str
    admin_password: str

    # Database Settings
    db_user: str
    db_password: str
    db_host: str
    db_name: str
    db_port: str

    # Path Settings
    images_basepath: str
    thumbnails_path: str
    annotations_path: str
    images_basepath_local: Optional[str] = None
    importer_copy_path: Optional[str] = None
    cfi_cache_path: Optional[str] = None

    @property
    def database(self) -> Dict[str, Optional[str]]:
        return {
            "user": self.db_user,
            "password": self.db_password,
            "host": self.db_host,
            "database": self.db_name,
            "port": self.db_port,
        }
    
    def make_orm_config(self) -> Dict[str, Optional[str]]:
        return {
            "database": self.database,
            "annotations_path": self.annotations_path,
            "thumbnails_path": self.thumbnails_path,
            "images_basepath": self.images_basepath,
            "images_basepath_local": self.images_basepath_local,
            "default_date": None,
            "importer_copy_path": self.importer_copy_path,
            "cfi_cache_path": self.cfi_cache_path,
            "secret_key": self.jwt_secret_key,
            "image_server_url": None,
            "trash_path": None,
        }

settings = Settings()
