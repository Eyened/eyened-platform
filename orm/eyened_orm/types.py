"""
SQLAlchemy type decorators for the eyened_orm package.
"""

from enum import Enum
from typing import Any, Optional, Type

from sqlalchemy import Enum as SAEnum
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.types import TypeDecorator


class OptionalEnum(TypeDecorator):
    """
    A TypeDecorator that wraps SAEnum and converts empty strings to None.
    
    This is useful for nullable enum columns where the database may store
    empty strings instead of NULL. When accessing the value via the ORM,
    empty strings are automatically converted to None.
    
    Usage:
        Sex: Mapped[Optional[SexEnum]] = mapped_column(OptionalEnum(SexEnum))
    """

    impl = SAEnum
    cache_ok = True

    def __init__(self, enum_class: Type[Enum], **kwargs):
        """Initialize with an enum class."""
        super().__init__(enum_class, **kwargs)
        self.enum_class = enum_class

    def process_result_value(self, value: Any, dialect: Any) -> Optional[Enum]:
        """
        Convert empty strings to None when reading from the database.

        Args:
            value: The value from the database
            dialect: SQLAlchemy dialect (unused)

        Returns:
            The enum value, or None if value is empty string or None
        """
        if value == '':
            return None
        return value


class CurrentTimestampOnUpdate(ColumnElement):
    """CURRENT_TIMESTAMP, which MySQL also maintains on UPDATE.

    As a ``server_default`` this makes the database maintain the column for
    every writer -- ORM, importer, CLI, raw SQL -- not just for writes through
    a mapped class. Other dialects fall back to a plain default so the same
    models can build a SQLite schema for tests.

    Pair it with ``server_onupdate=FetchedValue()``: without that the ORM does
    not know the database changed the column, and a flush without a commit
    serves the caller a stale timestamp.
    """

    inherit_cache = True


@compiles(CurrentTimestampOnUpdate)
def _render_current_timestamp(element, compiler, **kw) -> str:  # noqa: ANN001
    return "CURRENT_TIMESTAMP"


@compiles(CurrentTimestampOnUpdate, "mysql")
def _render_current_timestamp_mysql(element, compiler, **kw) -> str:  # noqa: ANN001
    return "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
