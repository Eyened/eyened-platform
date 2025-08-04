import enum
import re
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
)

from pydantic import create_model
from sqlalchemy import Column, select
from sqlalchemy.orm import Session
from sqlmodel import Field, SQLModel




def create_patch_model(name: str, base_model: type[SQLModel]) -> type[SQLModel]:
    """Create a Pydantic model with all fields optional useful for patching"""

    def get_field_type(field: Field) -> Any:
        if isinstance(field.annotation, type) and issubclass(
            field.annotation, enum.Enum
        ):
            # for enums, accept string values
            return Optional[str]
        return Optional[field.annotation]

    return create_model(
        name,
        __base__=SQLModel,
        **{
            field_name: (get_field_type(field), None)
            for field_name, field in base_model.model_fields.items()
            if not (field.json_schema_extra or {}).get("private", False)
        },
    )


def _convert_property_name(name: str) -> str:
    """Convert Python-style property names to capitalized camel case."""
    # Skip if the name is already in camel case
    if re.match(r"^[A-Z][a-zA-Z0-9]*$", name):
        return name

    # Split by underscore and capitalize each part
    def convert_part(part):
        if part == "id":
            return "ID"
        elif part == "images":
            return "ImageInstances"
        return part.capitalize()

    parts = name.split("_")

    # Capitalize each part and join
    return "".join(convert_part(part) for part in parts)


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
            raise AttributeError(
                f"'{obj_name}' has no attribute '{name}' or '{converted_name}'"
            )


T = TypeVar("T", bound="Base")


class Base(SQLModel):
    """Base class for all ORM models with common functionality."""

    # Common class variables
    _name_column: ClassVar[str | None] = None

    class Config:
        use_enum_values = False  # This tells Pydantic NOT to convert Enum to .value
        json_encoders = {enum.Enum: lambda x: x.name if isinstance(x, enum.Enum) else x}

    @property
    def session(self):
        """Get the session this object is attached to"""
        from sqlalchemy.orm import object_session
        session = object_session(self)
        if not session:
            raise ValueError("Object not attached to a session")
        return session

    @property
    def config(self):
        """Get config from session"""
        if not hasattr(self.session, 'config'):
            raise ValueError("Session not properly configured")
        return self.session.config

    @property
    def storage_manager(self):
        """Get storage manager from session"""
        if not hasattr(self.session, 'storage_manager'):
            raise ValueError("Session not properly configured")
        return self.session.storage_manager

    def __getattr__(self, name: str) -> Any:
        """Override attribute access to handle property name conversion.
        python style attribute names are converted to capitalized camel case SQL column names.
        """
        return _get_attribute_with_conversion(self, name)

    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional[T]:
        """Find an object by its name column value."""
        if cls._name_column is None:
            raise AttributeError(f"{cls.__name__} has no name column")
        kwargs = {cls._name_column: name}
        return cls.by_column(session, **kwargs)

    @classmethod
    def fetch_all(cls: Type[T], session: Session) -> List[T]:
        """Return all objects of the table."""
        return session.scalars(select(cls)).all()

    @classmethod
    def primary_keys(cls) -> List[Column]:
        """Return the list of primary key columns."""
        return list(cls.__table__.primary_key.columns)

    @classmethod
    def primary_key(cls) -> Column:
        """Return the single primary key column (raises if composite)."""
        pks = cls.primary_keys()
        if len(pks) != 1:
            raise ValueError(f"{cls.__name__} has a composite primary key: {pks}")
        return pks[0]

    @classmethod
    def by_id(cls: type[T], session: Session, id: int) -> Optional[T]:
        """Get object by single-column primary key."""
        pk_col = cls.primary_key()
        stmt = select(cls).where(pk_col == id)
        return session.scalar(stmt)

    @classmethod
    def by_ids(cls: Type[T], session: Session, ids: List[int]) -> List[T]:
        """Fetch objects by single-column primary key."""
        if not ids:
            return []
        pk_col = cls.primary_key()
        stmt = select(cls).where(pk_col.in_(set(ids)))
        return session.scalars(stmt).all()

    @classmethod
    def by_pk(cls: type[T], session: Session, pk: int | tuple) -> Optional[T]:
        """Generic lookup by primary key (supports single or composite keys via tuple)."""
        pks = cls.primary_keys()

        # Normalize pk into a tuple
        if not isinstance(pk, tuple):
            pk = (pk,)

        if len(pk) != len(pks):
            raise ValueError(
                f"{cls.__name__}.by_pk() expects {len(pks)} values, got {len(pk)}"
            )

        conditions = [col == val for col, val in zip(pks, pk)]
        stmt = select(cls).where(*conditions)
        return session.scalar(stmt)

    @classmethod
    def name_to_id(cls, session: Session) -> dict[str, int]:
        """Get a mapping of name column values to their IDs."""
        return {
            getattr(obj, cls._name_column): getattr(obj, cls.primary_key().name)
            for obj in cls.fetch_all(session)
        }

    @classmethod
    def by_column(cls: type[T], session: Session, **kwargs) -> Optional[T]:
        """Generic method to query by any column."""
        conditions = [getattr(cls, k) == v for k, v in kwargs.items()]
        stmt = select(cls).where(*conditions)
        return session.scalar(stmt)

    @classmethod
    def by_columns(cls: type[T], session: Session, **kwargs) -> List[T]:
        """Generic method to query by any columns."""
        conditions = [getattr(cls, k) == v for k, v in kwargs.items()]
        stmt = select(cls).where(*conditions)
        return session.scalars(stmt).all()

    @classmethod
    def columns(cls) -> List[Column]:
        """Return all columns of the table."""
        return cls.__table__.columns

    @classmethod
    def local_columns(cls) -> List[Column]:
        """Return columns that are not foreign keys."""
        return [c for c in cls.columns() if not c.foreign_keys]

    @classmethod
    def _base_joins(cls, statement):
        """Override this method to add custom joins to queries. """
        return statement
    
    @classmethod
    def where(cls: Type[T], session: Session, condition, include_inactive=False, **kwargs) -> List[T]:
        """Query objects with a custom condition and optional joins.
        
        Args:
            session: SQLAlchemy session
            condition: SQLAlchemy condition
            include_inactive: Whether to include inactive records (if model has Inactive column)
            **kwargs: Additional keyword arguments to pass to session.scalars()
        
        Returns:
            List of objects matching the condition
        """
        statement = select(cls)
        
        # Add inactive filter if model has Inactive column and include_inactive is False
        if not include_inactive and hasattr(cls, 'Inactive'):
            statement = statement.where(~cls.Inactive)
        
        # Apply custom joins
        statement = cls._base_joins(statement)
        
        # Add the main condition
        statement = statement.where(condition)
        
        return session.scalars(statement, **kwargs).all()

    def get_value(self, column: Column):
        val = getattr(self, column.name)
        if isinstance(val, enum.Enum):
            return val.name
        return val

    def to_dict(self) -> Dict[str, Any]:
        """Convert the object to a dictionary."""
        return {
            c.name: self.get_value(c)
            for c in self.columns()
            if not (self.__class__.model_fields[c.name].json_schema_extra or {}).get(
                "private", False
            )
        }

    def to_list(self) -> List[Any]:
        """Convert the object to a list of values."""
        return [self.get_value(c) for c in self.columns()]

    def __repr__(self) -> str:
        """String representation of the object."""
        args = ", ".join([f"{c.name}={getattr(self, c.name)}" for c in self.columns()])
        return f"{self.__class__.__name__}({args})"

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other
