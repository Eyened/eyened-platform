import datetime
import enum
import re
from typing import Any, Dict, List, Type, TypeVar, Tuple

from eyened_orm.utils.config import EyenedORMConfig
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.types import JSON
from sqlmodel import SQLModel
# MySQLWB naming convention.
# Additional functions: ForeignKeyIndex, CompositeUniqueConstraint (see below)
naming_convention = {
    "ix": "%(column_0_name)s",
    "uq": "%(column_0_name)s_UNIQUE",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s1",
    "pk": "%(column_0_name)s",
}

T = TypeVar("T", bound="Base")

def _convert_property_name(name: str) -> str:
    """Convert Python-style property names to capitalized camel case."""
    # Skip if the name is already in camel case
    if re.match(r'^[A-Z][a-zA-Z0-9]*$', name):
        return name
    
    # Split by underscore and capitalize each part
    def convert_part(part):
        if part == 'id':
            return 'ID'
        elif part == 'images':
            return 'ImageInstances'
        return part.capitalize()
    parts = name.split('_')

    # Capitalize each part and join
    return ''.join(convert_part(part) for part in parts)

def _get_attribute_with_conversion(obj, name: str) -> Any:
    """Helper function to get attribute with name conversion."""
    try:
        # First try to get the attribute directly
        return super(type(obj), obj).__getattribute__(name)
    except AttributeError:
        # If not found, try converting the name
        converted_name = _convert_property_name(name)
        try:
            return super(type(obj), obj).__getattribute__(converted_name)
        except AttributeError:
            # If still not found, raise the original AttributeError
            obj_name = obj.__name__ if isinstance(obj, type) else obj.__class__.__name__
            raise AttributeError(f"'{obj_name}' has no attribute '{name}' or '{converted_name}'")

class BaseMeta(type(DeclarativeBase)):
    """Metaclass to handle class-level attribute access for SQLAlchemy columns."""
    def __getattribute__(cls, name: str) -> Any:
        return _get_attribute_with_conversion(cls, name)

class Base(SQLModel):
    
    def __getattr__(self, name: str) -> Any:
        """Override attribute access to handle property name conversion."""
        return _get_attribute_with_conversion(self, name)

    @classmethod
    def fetch_all(cls: Type[T], session) -> List[T]:
        return session.query(cls).all()

    @classmethod
    def by_id(cls, session: Session, id: int):
        return session.scalar(select(cls).where(cls.__table__.primary_key.columns[0] == id))
    
    @classmethod
    def by_ids(cls, session: Session, ids: List[int]):
        return session.scalars(select(cls).where(cls.__table__.primary_key.columns[0].in_(ids)))
    
    @classmethod
    def by_column(cls, session: Session, column_name: str, value: Any):
        """Generic method to query by any column."""
        column = getattr(cls, column_name, None)
        if column is None:
            raise AttributeError(
                f"Column '{column_name}' does not exist on {cls.__name__}")
        return session.scalar(select(cls).where(column == value))

    @property
    def config(self):
        from eyened_orm.db import DBManager
        return DBManager._config

    @property
    def columns(self):
        return self.get_columns()

    @classmethod
    def get_columns(cls):
        return cls.__table__.columns

    @classmethod
    def filter_columns(cls):
        return [c for c in cls.get_columns() if not c.foreign_keys]

    @classmethod
    def init_class(cls, session=None, config=None):
        cls.session = session
        cls.config = config
        for subcls in cls.__subclasses__():
            fn = getattr(subcls, "init_class", lambda x: x)
            fn(session)
        

    def to_dict(self):
        return {c.name: to_dict(getattr(self, c.name)) for c in self.columns}

    def to_list(self):
        return [to_dict(getattr(self, c.name)) for c in self.columns]


def to_dict(attrib):
    if isinstance(attrib, enum.Enum):
        return attrib.name
    if isinstance(attrib, datetime.date):
        return str(attrib)
    else:
        return attrib
