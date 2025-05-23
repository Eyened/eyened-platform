from datetime import date
from pathlib import Path
from typing import Optional
import importlib.resources

from pydantic import Field
from pydantic_settings import (BaseSettings, PydanticBaseSettingsSource,
                               SettingsConfigDict)


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    """Database configuration settings"""
    user: str = Field(description="Database username", validation_alias="DB_USER")
    password: str = Field(description="Database password", validation_alias="DB_PASSWORD")
    host: str = Field(description="Database host", validation_alias="DB_HOST")
    database: str = Field(description="Database name", validation_alias="DB_NAME")
    port: str = Field(description="Database port", validation_alias="DB_PORT")
    raise_on_warnings: bool = True

    # this is just customizing pydantic settings to prioritize the .env file over the environment variables
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return dotenv_settings, env_settings, init_settings, file_secret_settings


class EyenedORMConfig(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    """Global configuration for Eyened platform"""
    # Database configuration
    database: Optional[DatabaseSettings] = None

    secret_key: str = Field(
        default="6f4b661212",
        description="Secret key used to generate hashes deterministically for password hashing and anonymisation and obfuscation of file names. "
                    "If not set, the db_id will be used as the filename"
    )
    
    # Basic configuration
    images_basepath: str = Field(
        default="/images",
        description="The folder containing local image data. "
                    "All local images linked in the eyened database should be stored in this folder (or descendants). "
                    "When running in Docker, this should be set to the host machine's path to the images. "
                    "The Docker container will mount this path to /images internally. "
                    "File references in the database will be relative to this folder. "
                    "This folder should be served if used with the eyened-viewer"
    )
    storage_basepath: str = Field(
        default="/storage",
        description="Base path for storage of annotations, thumbnails and trash. "
                    "Annotations will be stored in <storage_basepath>/annotations "
                    "thumbnails in <storage_basepath>/thumbnails "
                    "and trash in <storage_basepath>/trash"
    )
    
    @property
    def annotations_path(self) -> Path:
        return Path(self.storage_basepath) / "annotations"
    
    @property
    def thumbnails_path(self) -> Path:
        return Path(self.storage_basepath) / "thumbnails"
    
    @property
    def trash_path(self) -> Path:
        return Path(self.storage_basepath) / "trash"
    
    default_study_date: Optional[date] = Field(
        date(1970, 1, 1),
        description="Default date for new studies. "
                    "When the importer needs to create new studies and it does not receive a study date, "
                    "it will use this default date. Defaults to 1970-01-01"
    )

    # Extra options
    image_server_url: Optional[str] = Field(
        None,
        description="URL of the image server endpoint. "
                    "Used by the orm to generate urls to images as <image_server_url>/<dataset_identifier>"
    )
    
    # this is just customizing pydantic settings to prioritize the .env file over the environment variables
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return dotenv_settings, env_settings, init_settings, file_secret_settings


def get_config(env:str | None = None) -> EyenedORMConfig:
    """
    Load configuration from the appropriate environment file.
    
    Args:
        env: Environment to load configuration for (dev, prod, eyened, etc.)
        
    Returns:
        EyenedConfig: Configuration object
    """
    if env is None:
        env_file = f".env"
    else:
        env_file = f"{env}.env"
    
    package_root = Path(importlib.resources.files("eyened_orm"))   
    env_path = package_root / "environments" / env_file
    
    if not env_path.exists():
        raise FileNotFoundError(
            f"Environment file {env_file} does not exist at {env_path}. Did you forget to create it?"
        )
    
    db_settings = DatabaseSettings(_env_file=env_path, _env_file_encoding='utf-8')
    config = EyenedORMConfig(_env_file=env_path, _env_file_encoding='utf-8')
    config.database = db_settings
    
    return config
    
