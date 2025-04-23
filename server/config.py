from typing import Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    viewer_env: str = Field(default="production", env="VIEWER_ENV")
    # Authentication
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    access_token_duration: int = Field(
        env="PUBLIC_AUTH_TOKEN_DURATION",
        default=259200,  # 3 days in seconds
    )
    refresh_token_duration: int = Field(
        env="AUTH_REFRESH_TOKEN_DURATION",
        default=2592000,  # 30 days in seconds
    )

    # Default username and password for the admin user
    admin_username: str = Field(default=None, env="ADMIN_USERNAME")
    admin_password: str = Field(default=None, env="ADMIN_PASSWORD")

    # Database Settings
    db_engine_string: Optional[str] = Field(default=None, env="DB_ENGINE_STRING")
    db_user: Optional[str] = Field(default=None, env="DB_USER")
    db_password: Optional[str] = Field(default=None, env="DB_PASSWORD")
    db_host: Optional[str] = Field(default=None, env="DB_HOST")
    db_name: Optional[str] = Field(default=None, env="DB_NAME")
    db_port: Optional[str] = Field(default=None, env="DB_PORT")

    # Path Settings
    
    # for some reason, this is not working ???
    images_basepath: str = Field(default="/", env="IMAGES_BASEPATH")
    thumbnails_path: str = Field(default="/", env="THUMBNAILS_PATH")
    annotations_path: str = Field(default="/", env="ANNOTATIONS_DIR")
    importer_copy_path: str = Field(default="/", env="IMPORTER_COPY_PATH")
    cfi_cache_path: str = Field(default="/", env="CFI_CACHE_PATH")
    

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
            "default_date": None,
            "importer_copy_path": self.importer_copy_path,
            "cfi_cache_path": self.cfi_cache_path,
            "secret_key": None,
            "image_server_url": None,
            "trash_path": None,
        }

    class Config:
        # env_file = ".env"
        case_sensitive = False


# Create a global settings instance
settings = Settings()