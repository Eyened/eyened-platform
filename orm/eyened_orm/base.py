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

from eyened_orm.utils.zarr.manager import ZarrStorageManager
from eyened_orm.utils.table_printer import TablePrinter
from sqlalchemy import Column, Index, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Session


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
        return super(type(obj), obj).__getattribute__(name)
    except AttributeError:
        converted_name = _convert_property_name(name)
        try:
            return super(type(obj), obj).__getattribute__(converted_name)
        except AttributeError:
            obj_name = obj.__name__ if isinstance(obj, type) else obj.__class__.__name__
            raise AttributeError(
                f"'{obj_name}' has no attribute '{name}' or '{converted_name}'"
            )


T = TypeVar("T", bound="Base")


def ForeignKeyIndex(src_table: str, ref_table: str, column_name: str) -> Index:
    """Convenience helper to create a standard FK index name and definition."""
    return Index(f"fk_{src_table}_{ref_table}1_idx", column_name)


def CompositeUniqueConstraint(name: str, *column_names: str) -> UniqueConstraint:
    """Convenience helper to define a composite unique constraint."""
    return UniqueConstraint(*column_names, name=name)


class Base(DeclarativeBase):
    """SQLAlchemy Declarative base with common helpers and utilities."""

    _name_column: ClassVar[str | None] = None

    @property
    def session(self):
        """Get the session this object is attached to."""
        from sqlalchemy.orm import object_session

        session = object_session(self)
        if not session:
            raise ValueError("Object not attached to a session")
        return session

    @property
    def config(self):
        """Get config from the attached session."""
        if not hasattr(self.session, "config"):
            raise ValueError("Session not properly configured")
        return self.session.config

    @property
    def storage_manager(self) -> ZarrStorageManager:
        """Get storage manager from the attached session."""
        if not hasattr(self.session, "storage_manager"):
            raise ValueError("Session not properly configured")
        return self.session.storage_manager

    def __getattr__(self, name: str) -> Any:
        """Resolve missing attributes by converting snake_case to CamelCase column names."""
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
    def _build_where_stmt(cls, **kwargs):
        """Build a select statement with where conditions from kwargs."""
        conditions = [getattr(cls, k) == v for k, v in kwargs.items()]
        return select(cls).where(*conditions)

    @classmethod
    def by_column(cls: type[T], session: Session, **kwargs) -> Optional[T]:
        """Generic method to query by any column."""
        return session.scalar(cls._build_where_stmt(**kwargs))

    @classmethod
    def by_columns(cls: type[T], session: Session, **kwargs) -> List[T]:
        """Generic method to query by any columns."""
        return session.scalars(cls._build_where_stmt(**kwargs)).all()

    @classmethod
    def get_or_create(
        cls: type[T],
        session: Session,
        match_by: Dict[str, Any],
        create_kwargs: Optional[Dict[str, Any]] = None,
        must_match: Optional[Dict[str, Any]] = None,
        verbose: bool = False,
    ) -> T:
        """
        Get an existing instance matching the criteria, or create a new one if not found.

        Args:
            session: SQLAlchemy session.
            match_by: Dict of field names to values to match on (for "get").
            create_kwargs: Dict of values to use when creating (if not exist).
                If None, uses match_by values.
            must_match: Optional dict of fields that must match *if* found, else raises error.
                Useful for type checking or ensuring consistency.
            verbose: If True, print log messages about found/created instances.

        Returns:
            The found or created instance.

        Raises:
            ValueError: If an existing instance is found but doesn't match must_match criteria.
        """
        # Try to find existing instance
        instance = cls.by_column(session, **match_by)

        display_name = cls.__name__
        if instance:
            # Optionally, check for required matches (e.g. data type)
            if must_match:
                errors = [
                    f"{attr}: existing={actual}, requested={expect}"
                    for attr, expect in must_match.items()
                    if (actual:= getattr(instance, attr)) != expect
                ]
                if errors:
                    raise ValueError(
                        f"{display_name} exists with different parameters: "
                        + "; ".join(errors)
                    )
            if verbose:
                print(f"Found existing {display_name}: {repr(instance)}")
            return instance

        # Create new instance
        create_kwargs = create_kwargs or match_by
        instance = cls(**create_kwargs)
        session.add(instance)
        session.flush()
        if verbose:
            print(f"Created {display_name}: {repr(instance)}")
        return instance

    @classmethod
    def columns(cls) -> List[Column]:
        """Return all columns of the table."""
        return cls.__table__.columns

    @classmethod
    def all_columns(cls) -> List[Column]:
        """Return all columns including columns from parent classes in the inheritance hierarchy."""
        columns = []
        seen_names = set()
        # Traverse MRO to collect columns from all Base subclasses
        for base_cls in cls.__mro__:
            if issubclass(base_cls, Base) and hasattr(base_cls, "__table__"):
                for col in base_cls.__table__.columns:
                    # Avoid duplicates (child classes may redefine parent columns)
                    if col.name not in seen_names:
                        columns.append(col)
                        seen_names.add(col.name)
        return columns

    @classmethod
    def local_columns(cls) -> List[Column]:
        """Return columns that are not foreign keys."""
        return [c for c in cls.columns() if not c.foreign_keys]

    @classmethod
    def _base_joins(cls, statement):
        """Override this method to add custom joins to queries."""
        return statement

    @classmethod
    def where(
        cls: Type[T], session: Session, condition, include_inactive=False, **kwargs
    ) -> List[T]:
        """Query objects with a custom condition and optional joins."""
        statement = select(cls)

        if not include_inactive and hasattr(cls, "Inactive"):
            statement = statement.where(~cls.Inactive)

        statement = cls._base_joins(statement)
        statement = statement.where(condition)

        return session.scalars(statement, **kwargs).all()

    def get_value(self, column: Column):
        val = getattr(self, column.name)
        if isinstance(val, enum.Enum):
            return val.value
        return val

    def to_dict(self, include_parents: bool = False) -> Dict[str, Any]:
        """Convert the object to a dictionary, skipping columns marked private.

        Args:
            include_parents: If True, include columns from parent classes in inheritance hierarchy.
        """
        columns = self.all_columns() if include_parents else self.columns()
        return {
            c.name: self.get_value(c)
            for c in columns
            if not (getattr(c, "info", None) or {}).get("private", False)
        }

    def to_list(self) -> List[Any]:
        """Convert the object to a list of values."""
        return [self.get_value(c) for c in self.columns()]

    def __repr__(self) -> str:
        """String representation of the object."""
        args = ", ".join([f"{c.name}={getattr(self, c.name)}" for c in self.columns()])
        return f"{self.__class__.__name__}({args})"

    def _repr_html_(self) -> str:
        """HTML representation for Jupyter notebook display in table format."""
        pk_values = tuple(self.get_value(pk) for pk in self.primary_keys())
        pk_str = pk_values[0] if len(pk_values) == 1 else pk_values
        printer = TablePrinter(title=f"{self.__class__.__name__} {pk_str}")
        return printer.print_table(self.to_dict(include_parents=True))

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other
