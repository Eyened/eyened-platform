import datetime
import enum
from typing import Any, Dict, List, Type, TypeVar, Tuple

from sqlalchemy import Index, MetaData, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.types import JSON

# MySQLWB naming convention.
# Additional functions: ForeignKeyIndex, CompositeUniqueConstraint (see below)
naming_convention = {
    "ix": "%(column_0_name)s",
    "uq": "%(column_0_name)s_UNIQUE",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s1",
    "pk": "%(column_0_name)s",
}

metadata = MetaData(naming_convention=naming_convention)
T = TypeVar("T", bound="Base")


class Base(DeclarativeBase):
    metadata = metadata  # Attach the metadata with the naming convention
    type_annotation_map = {Dict[str, Any]: JSON}
    config = None

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


def ForeignKeyIndex(referencing_table: str, referred_table: str, fk_column: str):
    """Helper function to create a ForeignKey index with MySQLWB naming convention."""
    fk_index_name = f"fk_{referencing_table}_{referred_table}1_idx"
    return Index(fk_index_name, fk_column)


def CompositeUniqueConstraint(column1: str, column2: str):
    """Helper function to create a CompositeUniqueConstraint with MySQLWB naming convention."""
    constraint_name = f"{column1}{column2}_UNIQUE"
    return UniqueConstraint(column1, column2, name=f"{constraint_name}")


def CompositeUniqueConstraintMulti(columns: Tuple[str]):
    """Helper function to create a CompositeUniqueConstraint with MySQLWB naming convention."""
    constraint_name = "".join(columns) + "_UNIQUE"
    return UniqueConstraint(*columns, name=f"{constraint_name}")


def to_dict(attrib):
    if isinstance(attrib, enum.Enum):
        return attrib.name
    if isinstance(attrib, datetime.date):
        return str(attrib)
    else:
        return attrib
