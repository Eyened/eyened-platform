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

    # Database Settings
    db_engine_string: Optional[str] = Field(default=None, env="DB_ENGINE_STRING")
    db_user: Optional[str] = Field(default=None, env="DB_USER")
    db_password: Optional[str] = Field(default=None, env="DB_PASSWORD")
    db_host: Optional[str] = Field(default=None, env="DB_HOST")
    db_name: Optional[str] = Field(default=None, env="DB_NAME")
    db_port: Optional[str] = Field(default=None, env="DB_PORT")

    # Path Settings
    
    # for some reason, this is not working ???
    # annotations_path: str = Field(default="/", env="ANNOTATIONS_DIR")
    annotations_path: str = Field(os.environ.get('ANNOTATIONS_DIR', '/'))

    @property
    def database(self) -> Dict[str, Optional[str]]:
        return {
            "user": self.db_user,
            "password": self.db_password,
            "host": self.db_host,
            "database": self.db_name,
            "port": self.db_port,
        }

    class Config:
        # env_file = ".env"
        case_sensitive = False


# Create a global settings instance
settings = Settings()