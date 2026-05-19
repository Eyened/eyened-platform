from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.sqltypes import BLOB, JSON


def _add_repo_orm_to_syspath() -> None:
    """
    Make `import eyened_orm` work when running from a git checkout without installation.

    This matches the unit test setup in `orm/tests/conftest.py`.
    """

    repo_root = Path(__file__).resolve().parents[2]
    orm_root = repo_root / "orm"
    if str(orm_root) not in sys.path:
        sys.path.insert(0, str(orm_root))


def _install_sqlite_type_shims() -> None:
    """
    The ORM targets MySQL/MariaDB and uses MySQL-only types in a few models.
    For in-memory SQLite use we compile these into compatible SQLite types.
    """

    @compiles(LONGBLOB, "sqlite")
    def _compile_longblob_sqlite(element, compiler, **kw):  # noqa: ANN001
        return compiler.visit_BLOB(BLOB(), **kw)

    @compiles(MySQLJSON, "sqlite")
    def _compile_mysqljson_sqlite(element, compiler, **kw):  # noqa: ANN001
        return compiler.process(JSON(), **kw)


def create_sqlite_memory_engine():
    """
    Create an in-memory SQLite engine compatible with the EyeNED ORM schema.

    Uses `StaticPool` so multiple sessions can share one in-memory database.
    """

    _add_repo_orm_to_syspath()

    # Importing registers all ORM models on Base.metadata.
    import eyened_orm  # noqa: F401
    from eyened_orm.base import Base

    _install_sqlite_type_shims()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def create_sqlite_memory_sessionmaker(*, expire_on_commit: bool = False):
    """Return a `sessionmaker` bound to an in-memory SQLite engine."""

    engine = create_sqlite_memory_engine()
    return sessionmaker(
        bind=engine,
        future=True,
        expire_on_commit=expire_on_commit,
        class_=Session,
    )

