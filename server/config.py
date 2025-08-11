import os
from typing import Optional
import yaml
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from eyened_orm.utils.config import EyenedORMConfig

class Settings(EyenedORMConfig):
    # IMPORTANT: the base fields in this file must match environment variable names exactly (with the exception of case) unless otherwise specified with validation_alias
    # NOTE: that this file also inherits from EyenedORMConfig
    # Pydantic will take care of reading the environment internally
    
    # Server-specific configuration with non-redundant fields
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # Default username and password for the admin user
    admin_username: str
    admin_password: str

    database_root_password: Optional[str] = Field(description="Database root password", validation_alias="DATABASE_ROOT_PASSWORD", default=None)

    # Print settings for debugging purposes - hide password and secret key
    def __str__(self):
        settings_dict = self.model_dump()
        settings_dict['secret_key'] = '***HIDDEN***'
        settings_dict['admin_password'] = '***HIDDEN***'
        settings_dict['database']['password'] = '***HIDDEN***'
        return yaml.dump(settings_dict, default_flow_style=False)


settings = Settings()
if settings.database.user == '' or settings.database.password == '':
    settings.database.user = "root"
    settings.database.password = settings.database_root_password