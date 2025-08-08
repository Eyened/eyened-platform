import sys
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

class DatabaseSettings(BaseSettings): 
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    password: str = Field(description="Database password", validation_alias="DATABASE_PASSWORD")
    user: str = Field(description="Database user", validation_alias="DATABASE_USER")
    host: str = Field(description="Database host", validation_alias="DATABASE_HOST")
    port: str = Field(description="Database port", validation_alias="DATABASE_PORT")
    database: str = Field(description="Database name", validation_alias="DATABASE_NAME")

if __name__ == "__main__":
    # Check if path argument is provided
    if len(sys.argv) < 2:
        print("Usage: python set_connection_string.py <path_to_env_file>")
        print("Example: python set_connection_string.py ../../dev/.env")
        sys.exit(1)
    
    env_path = Path(sys.argv[1]).resolve()
    
    if not env_path.exists():
        print(f"Error: Environment file not found at {env_path}")
        sys.exit(1)
    
    print(f"Loading environment from: {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)

    settings = DatabaseSettings()
    
    # Use absolute path for cleaner output
    filename = Path(__file__).parent.resolve() / "alembic.ini.sample"
    print(f'Reading alembic template: {filename}')

    with open(filename, 'r') as configfile:
        lines = configfile.readlines()

    new_url = f'mysql+pymysql://{settings.user}:{settings.password}@{settings.host}:{settings.port}/{settings.database}'
    print(f'New connection URL: {new_url}')

    # Check if we found and updated the line
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith('sqlalchemy.url'):
            lines[i] = f'sqlalchemy.url = {new_url}\n'
            updated = True
            break
    
    if not updated:
        print(f"Warning: Could not find 'sqlalchemy.url' line in {filename}")
        sys.exit(1)

    filename = Path(__file__).parent.resolve() / "alembic.ini"
    with open(filename, 'w') as configfile:
        configfile.writelines(lines)
    
    print("✅ Connection string updated successfully!")
