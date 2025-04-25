import importlib
import os
from pathlib import Path
from typing import Optional
from datetime import date
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    """Database configuration settings"""
    user: str = Field(description="Database username", validation_alias="DB_USER")
    password: str = Field(description="Database password", validation_alias="DB_PASSWORD")
    host: str = Field(description="Database host", validation_alias="DB_HOST")
    database: str = Field(description="Database name", validation_alias="DB_NAME")
    port: str = Field(description="Database port", validation_alias="DB_PORT")
    raise_on_warnings: bool = True


class EyenedORMConfig(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    """Global configuration for Eyened platform"""
    # Database configuration
    database: DatabaseSettings | None = None
    
    # Basic configuration
    annotations_path: str = Field(
        description="Path to the folder containing annotations. "
                    "Used by the platform for reading and writing annotations"
    )
    thumbnails_path: str = Field(
        description="Folder containing the thumbnail structure. "
                    "Used by the ORM to read thumbnails and by the importer to write thumbnails on insertion"
    )
    
    # Configuration for the importer
    images_basepath: str = Field(
        description="The folder containing local image data. "
                    "All local images linked in the eyened database should be stored in this folder (or descendants). "
                    "File references in the database will be relative to this folder. "
                    "This folder should be served if used with the eyened-viewer"
    )

    images_basepath_local: Optional[str] = Field(
        None,
        description="The local path to images_basepath to be used to resolve image paths in the ORM. This is different from images_basepath in that images_basepath is the path on the server (outside of the container) and images_basepath_local is the path inside the container (to a mounted volume)."
    )
    default_study_date: Optional[date] = Field(
        None,
        description="Default date for new studies. "
                    "When the importer needs to create new studies and it does not receive a study date, "
                    "it will use this default date. Defaults to 1970-01-01"
    )
    importer_copy_path: Optional[str] = Field(
        None,
        description="Folder for the importer to copy images to when ran with copy_files=True. "
                    "Only required when running the importer with the copy_files=True option. "
                    "It should be a descendant of images_basepath"
    )
    cfi_cache_path: Optional[str] = Field(
        None,
        description="Path of a cache for fundus images. "
                    "Used by the importer to write a preprocessed version of the images. "
                    "The cache is only written if this path is set"
    )
    secret_key: Optional[str] = Field(
        None,
        description="Secret key used to generate hashes deterministically for anonymisation and obfuscation of file names. "
                    "If not set, the db_id will be used as the filename"
    )
    
    # Extra options
    image_server_url: Optional[str] = Field(
        None,
        description="URL of the image server endpoint. "
                    "Used by the orm to generate urls to images as <image_server_url>/<dataset_identifier>"
    )
    trash_path: Optional[str] = Field(
        None,
        description="Folder to move deleted annotations / form_annotations to when deleted from the ORM. "
                    "If not set, the annotations will not be moved to a trash folder"
    )


def get_config(env="dev") -> EyenedORMConfig:
    """
    Load configuration from the appropriate environment file.
    
    Args:
        env: Environment to load configuration for (dev, prod, eyened, etc.)
        
    Returns:
        EyenedConfig: Configuration object
    """
    env_file = f"{env}.env"
    dir_path = Path(__file__).parent.parent.parent.parent
    env_path = dir_path / env_file
    
    if not env_path.exists():
        raise FileNotFoundError(
            f"Environment file {env_file} does not exist at {env_path}. Did you forget to create it?"
        )
    
    db_settings = DatabaseSettings(_env_file=env_path, _env_file_encoding='utf-8')
    config = EyenedORMConfig(_env_file=env_path, _env_file_encoding='utf-8')
    config.database = db_settings
    
    return config
    
