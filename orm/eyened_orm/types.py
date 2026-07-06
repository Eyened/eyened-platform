"""
SQLAlchemy type decorators for the eyened_orm package.
"""

from enum import Enum
from typing import Any, Optional, Type

from sqlalchemy import Enum as SAEnum
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

