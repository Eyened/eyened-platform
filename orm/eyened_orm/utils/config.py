from datetime import date
from typing import Optional, Callable, Tuple

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

# just adding the from_dict method to BaseSettings to allow for creating settings from a dict
# without using env variables
class MyBaseSettings(BaseSettings):
    @classmethod
    def from_dict(cls, values: dict) -> "MyBaseSettings":
        class NoEnvSettings(cls):
            @classmethod
            def settings_customise_sources(
                inner_cls,
                __cls,
                *,
                init_settings: Callable[..., dict],
                env_settings: Callable[..., dict],
                dotenv_settings: Callable[..., dict],
                file_secret_settings: Callable[..., dict],
            ) -> Tuple[Callable[..., dict], ...]:
                # Only use values passed to constructor
                return (init_settings,)

        return NoEnvSettings(**values)


class DatabaseSettings(MyBaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, extra="ignore", populate_by_name=True
    )

    """Database configuration settings"""
    user: str = Field(description="Database username", validation_alias="DATABASE_USER")
    password: str = Field(
        description="Database password", validation_alias="DATABASE_PASSWORD"
    )
    host: str = Field(description="Database host", validation_alias="DATABASE_HOST")
    database: str = Field(description="Database name", validation_alias="DATABASE_NAME")
    port: int = Field(description="Database port", validation_alias="DATABASE_PORT")
    raise_on_warnings: bool = True


class EyenedORMConfig(MyBaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    """Global configuration for Eyened platform"""
    # Database configuration
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    # Secret key used to generate hashes deterministically for obfuscation of file names.
    secret_key: str = "6f4b661212"

    # File system configuration
    images_basepath: str = Field(
        default="/images",
        description="The folder containing local image data. "
        "All local images linked in the eyened database should be stored in this folder (or descendants). "
        "File references in the database will be relative to this folder. "
        "This folder should be served if used with the eyened-viewer",
    )
    segmentations_zarr_store: str = Field(
        default="/storage/segmentations.zarr",
        description="Path to the zarr store containing segmentations. "
        "Used by the platform for reading and writing segmentations",
    )
    thumbnails_path: str = Field(
        default="/storage/thumbnails",
        description="Folder containing the thumbnail structure. "
        "Used by the ORM to read thumbnails and by the importer to write thumbnails on insertion",
    )

    default_study_date: Optional[date] = Field(
        date(1970, 1, 1),
        description="Default date for new studies. "
        "When the importer needs to create new studies and it does not receive a study date, "
        "it will use this default date. Defaults to 1970-01-01",
    )

    # Extra options
    cfi_cache_path: Optional[str] = Field(
        default=None,
        description="Path of a cache for fundus images. "
        "Used by the importer to write a preprocessed version of the images.",
    )
    image_server_url: Optional[str] = Field(
        None,
        description="URL of the image server endpoint. "
        "Used by the orm to generate urls to images as <image_server_url>/<dataset_identifier>",
    )
