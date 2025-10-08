from dataclasses import dataclass, field, fields
from datetime import date
from typing import Optional, Mapping, Union, Any, get_origin, get_args
from pathlib import Path


def env_field(env_name: str, required: bool = True, default: Any = None):
    """Create a dataclass field with environment variable metadata."""
    metadata = {"env_name": env_name, "required": required}
    return field(default=default, metadata=metadata)

def _get_env_value(env: Mapping[str, str], field_info) -> Any:
    """Extract and convert environment value for a field."""
    metadata = field_info.metadata
    env_name = metadata["env_name"]
    required = metadata["required"]
    
    value = env.get(env_name)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {env_name}")
    
    if not value:
        return field_info.default
    
    # Type conversion
    field_type = field_info.type
    
    # Handle Optional types
    if get_origin(field_type) is Union:
        # Check if it's Optional[T] -> Union[T, None]
        args = get_args(field_type)
        if len(args) == 2 and type(None) in args:
            actual_type = args[0] if args[1] is type(None) else args[1]
        else:
            actual_type = field_type
    else:
        actual_type = field_type
    
    # Special handling for different types
    if actual_type == int:
        try:
            return int(value)
        except ValueError as e:
            raise ValueError(f"{env_name} must be an integer, got: {value}") from e
    elif actual_type == bool:
        return value.lower() in ("true", "1", "yes", "on")
    elif actual_type == date:
        try:
            return date.fromisoformat(value)
        except ValueError as e:
            raise ValueError(f"{env_name} must be YYYY-MM-DD format, got: {value}") from e
    elif actual_type == Path:
        return Path(value)
    else:
        return value


def _is_dataclass_like(cls) -> bool:
    """Check if a class is a dataclass that uses env_field."""
    return hasattr(cls, '__dataclass_fields__') and any(
        hasattr(field_info.metadata, 'get') and field_info.metadata.get('env_name')
        for field_info in fields(cls)
    )


def from_env(cls, env: Mapping[str, str]) -> Any:
    """Generic function to create dataclass instances from environment variables."""
    field_values = {}
    
    for field_info in fields(cls):
        field_type = field_info.type
        
        # Check if this field type is a dataclass that uses env_field
        if _is_dataclass_like(field_type):
            # Recursively handle nested dataclass
            field_values[field_info.name] = from_env(field_type, env)
        else:
            # Handle regular field with environment variable
            field_values[field_info.name] = _get_env_value(env, field_info)
    
    return cls(**field_values)


def from_env_file(cls, path: Union[str, Path]) -> Any:
    """Generic function to create dataclass instances from .env files."""
    from dotenv import dotenv_values
    
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")
    
    values = dotenv_values(dotenv_path=env_path)
    # Filter out None values
    filtered = {k: v for k, v in values.items() if v is not None}
    return from_env(cls, filtered)


def create(cls, source: Optional[Union[str, Path, Mapping[str, str]]] = None, **kwargs) -> Any:
    """
    Generic factory function to create dataclass instances from various sources.
    
    Args:
        cls: The dataclass class to instantiate
        source: Can be None (use current env), str/Path (env file), or Mapping (env dict)
        **kwargs: Additional parameters to override defaults
    
    Returns:
        Instance of cls
    """
    import os
    
    if source is None:
        env = os.environ
    elif isinstance(source, (str, Path)):
        from dotenv import dotenv_values
        env_path = Path(source)
        if not env_path.exists():
            raise FileNotFoundError(f"Environment file not found: {env_path}")
        values = dotenv_values(dotenv_path=env_path)
        env = {k: v for k, v in values.items() if v is not None}
    elif isinstance(source, Mapping):
        env = source
    else:
        raise ValueError(f"Invalid source type: {type(source)}")
    
    instance = from_env(cls, env)
    
    # Apply any overrides
    for key, value in kwargs.items():
        if hasattr(instance, key):
            setattr(instance, key, value)
        else:
            raise ValueError(f"Unknown configuration parameter: {key}")
    
    return instance


def configurable(cls=None, **dataclass_kwargs):
    """
    Class decorator that combines @dataclass with automatic addition of from_env, 
    from_env_file, and create class methods.
    
    Usage:
        @configurable
        class MyConfig:
            field: str = env_field("MY_FIELD")
    
    Or with dataclass options:
        @configurable(frozen=True)
        class MyConfig:
            field: str = env_field("MY_FIELD")
    """
    def decorator(cls):
        # Apply dataclass decorator first
        cls = dataclass(cls, **dataclass_kwargs)
        
        # Add the environment loading methods
        cls.from_env = classmethod(lambda cls, env: from_env(cls, env))
        cls.from_env_file = classmethod(lambda cls, path: from_env_file(cls, path))
        cls.create = classmethod(lambda cls, source=None, **kwargs: create(cls, source, **kwargs))
        
        return cls
    
    # Handle both @configurable and @configurable(...) usage
    if cls is None:
        return decorator
    else:
        return decorator(cls)


@configurable
class DatabaseSettings:
    user: str = env_field("DATABASE_USER")
    password: str = env_field("DATABASE_PASSWORD")
    host: str = env_field("DATABASE_HOST")
    database: str = env_field("DATABASE_NAME")
    port: int = env_field("DATABASE_PORT")
    raise_on_warnings: bool = env_field("DATABASE_RAISE_ON_WARNINGS", required=False, default=True)


@configurable
class EyenedORMConfig:
    database: DatabaseSettings
    secret_key: str = env_field("SECRET_KEY")
    images_basepath: Path = env_field("IMAGES_BASEPATH", required=False, default=Path("/images"))
    segmentations_zarr_store: Path = env_field("SEGMENTATIONS_ZARR_STORE", required=False, default=Path("/storage/segmentations.zarr"))
    thumbnails_path: Path = env_field("THUMBNAILS_PATH", required=False, default=Path("/storage/thumbnails"))
    annotations_path: Path = env_field("ANNOTATIONS_PATH", required=False, default=Path("/storage/annotations"))
    default_study_date: Optional[date] = env_field("DEFAULT_STUDY_DATE", required=False, default=date(1970, 1, 1))
    cfi_cache_path: Optional[Path] = env_field("CFI_CACHE_PATH", required=False, default=None)
    image_server_url: Optional[str] = env_field("IMAGE_SERVER_URL", required=False, default=None)


