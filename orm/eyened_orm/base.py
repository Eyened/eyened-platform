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
    Iterable,
)
from collections.abc import Iterable

from eyened_orm.utils.zarr.manager import ZarrStorageManager
from eyened_orm.utils.table_printer import TablePrinter
from sqlalchemy import Column, Index, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Session, InstrumentedAttribute


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
    def fetch_all(
        cls: Type[T],
        session: Session,
        limit: int | None = None,
        offset: int | None = None,
    ) -> List[T]:
        """Return all objects of the table."""
        stmt = select(cls)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return session.scalars(stmt).all()

    @classmethod
    def query_column(
        cls,
        session: Session,
        column: Column | InstrumentedAttribute | str,
        distinct: bool = True,
        where: Any = None,
    ) -> List[Any]:
        """
        Query distinct values from a single column of this table, with optional filtering.

        Args:
            session: SQLAlchemy session.
            column: Column attribute (e.g., cls.ColumnName) or column name string.
            distinct: If True, return only distinct values (default: True).
            where: Optional SQLAlchemy filter expression(s) to apply.

        Returns:
            List of column values.

        Example:
            >>> Creator.query_column(session, Creator.CreatorName)
            ['Alice', 'Bob', 'Charlie']
            >>> Project.query_column(session, 'ProjectName', distinct=False)
            ['Project1', 'Project1', 'Project2', ...]
            >>> Creator.query_column(session, Creator.CreatorName, where=(Creator.Inactive == False))
            ['Alice', 'Bob']
        """
        if isinstance(column, str):
            column = getattr(cls, column)
        return cls.select(session, column, distinct=distinct, where=where)

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
    def by_ids(cls: Type[T], session: Session, ids: Iterable[int]) -> Dict[int, T]:
        """Fetch objects by single-column primary key."""
        if not ids:
            return {}
        pk_col = cls.primary_key()
        stmt = select(cls).where(pk_col.in_(set(ids)))
        return {getattr(obj, pk_col.name): obj for obj in session.scalars(stmt).all()}

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
    def _build_conditions(cls, **filters):
        """Build WHERE conditions from kwargs.

        Automatically uses in_ operator for iterable values (list, tuple, set) but not strings.

        Returns:
            List of SQLAlchemy condition expressions.
        """

        conditions = []
        for k, v in filters.items():
            col = getattr(cls, k)
            # Use in_ for iterables (but not strings)
            if isinstance(v, Iterable) and not isinstance(v, str):
                conditions.append(col.in_(v))
            else:
                conditions.append(col == v)
        return conditions

    @classmethod
    def _build_where_stmt(cls, **kwargs):
        """Build a select statement with where conditions from kwargs.

        Automatically uses in_ operator for iterable values (list, tuple, set) but not strings.
        """
        conditions = cls._build_conditions(**kwargs)
        return select(cls).where(*conditions)

    @classmethod
    def by_column(cls: type[T], session: Session, **kwargs) -> Optional[T]:
        """Generic method to query by any column."""
        return session.scalar(cls._build_where_stmt(**kwargs))

    @classmethod
    def by_columns(cls: type[T], session: Session, **kwargs) -> List[T]:
        """
        Generic method to query by any columns.

        Automatically uses in_ operator when values are iterables (list, tuple, set) but not strings.

        Example:
            >>> AttributeValue.by_columns(session, ModelID=32, ImageInstanceID=selected_images)
            # Uses: ModelID == 32 AND ImageInstanceID.in_(selected_images)
        """
        return session.scalars(cls._build_where_stmt(**kwargs)).all()

    @classmethod
    def select(
        cls,
        session: Session,
        *columns: Column | InstrumentedAttribute | str,
        distinct: bool = False,
        where: Any = None,
        **filters,
    ) -> List[Any] | List[tuple]:
        """
        Select specific columns from the table with optional filtering.

        SQL-like interface for selecting column values. Automatically uses IN operator
        for iterable values (list, tuple, set) but not strings.

        Args:
            session: SQLAlchemy session.
            *columns: One or more column attributes (e.g., cls.ColumnName) or column name strings.
                If one column: returns list[Any]
                If multiple columns: returns list[tuple]
            distinct: If True, return only distinct values (default: False).
            where: Optional SQLAlchemy filter expression(s) to apply in addition to filters.
            **filters: Column filters as kwargs. Automatically uses IN for iterables.

        Returns:
            list[Any] for single column, list[tuple] for multiple columns.

        """
        if not columns:
            raise ValueError("At least one column must be specified")

        # Convert string column names to column attributes
        resolved_columns = [
            getattr(cls, col) if isinstance(col, str) else col for col in columns
        ]

        stmt = select(*resolved_columns)

        if filters:
            conditions = cls._build_conditions(**filters)
            stmt = stmt.where(*conditions)

        if where is not None:
            stmt = stmt.where(where)

        if distinct:
            stmt = stmt.distinct()

        if len(resolved_columns) == 1:
            return session.scalars(stmt).all()
        else:
            return session.execute(stmt).all()

    @classmethod
    def get_or_create(
        cls: type[T],
        session: Session,
        match_by: Dict[str, Any],
        create_kwargs: Optional[Dict[str, Any]] = None,
        must_match: Optional[Dict[str, Any]] = None,
        update_values: Optional[Dict[str, Any]] = None,
        verbose: bool = False,
    ) -> T:
        """
        Get an existing instance matching the criteria, or create a new one if not found.
        Optionally update the instance if found or set values when creating.

        Args:
            session: SQLAlchemy session.
            match_by: Dict of field names to values to match on (for "get").
            create_kwargs: Dict of values to use when creating (if not exist).
                If None, uses match_by values.
            must_match: Optional dict of fields that must match *if* found, else raises error.
                Useful for type checking or ensuring consistency.
            update_values: Optional dict of fields to update (if found) or set (if created).
            verbose: If True, print log messages about found/created instances.

        Returns:
            The found or created instance.

        Raises:
            ValueError: If an existing instance is found but doesn't match must_match criteria.
        """
        # Try to find existing instance
        instance = cls.by_column(session, **match_by)

        display_name = cls.__name__
        is_new = False
        if instance:
            # Optionally, check for required matches (e.g. data type)
            if must_match:
                errors = [
                    f"{attr}: existing={actual}, requested={expect}"
                    for attr, expect in must_match.items()
                    if (actual := getattr(instance, attr)) != expect
                ]
                if errors:
                    raise ValueError(
                        f"{display_name} exists with different parameters: "
                        + "; ".join(errors)
                    )
        else:
            # Create new instance
            instance = cls(**(match_by | (create_kwargs or {})))
            session.add(instance)
            is_new = True

        # Apply updates if provided (works for both existing and new instances)
        if update_values is not None:
            for key, value in update_values.items():
                setattr(instance, key, value)

        session.flush()

        if verbose:
            action = "Created" if is_new else "Found existing"
            print(f"{action} {display_name}: {repr(instance)}")
        return instance

    @classmethod
    def upsert(
        cls: type[T],
        session: Session,
        match_by: Dict[str, Any],
        update_values: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Update an existing instance matching the criteria, or create a new one if not found.

        This is a convenience wrapper around get_or_create that always applies update_values.

        Args:
            session: SQLAlchemy session.
            match_by: Dict of field names to values to match on (for finding existing record).
            update_values: Dict of field names to values to update (if found) or set (if created).

        Returns:
            The updated or created instance.

        """
        return cls.get_or_create(session, match_by, update_values=update_values)

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
        cols = self.all_columns()  # include parent-table columns (joined inheritance)
        args = ", ".join([f"{c.name}={self.get_value(c)}" for c in cols])
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
