from __future__ import annotations

from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.sqltypes import BLOB, JSON


def _add_repo_orm_to_syspath() -> None:
    """
    Make `import eyened_orm` work when running from a git checkout without installation.
    """

    orm_root = Path(__file__).resolve().parents[2]
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

    @event.listens_for(engine, "connect")
    def _sqlite_set_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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


@pytest.fixture(scope="function")
def engine():
    """In-memory SQLite engine shared by all sessions in a test."""
    return create_sqlite_memory_engine()


@pytest.fixture(scope="function")
def SessionLocal(engine):
    # expire_on_commit=True mirrors the production session factory
    # (orm/eyened_orm/db.py uses SQLAlchemy's default True), so tests reproduce
    # production's commit-time expiry: state loaded before a commit is reloaded
    # from the DB on next access, rather than lingering stale in the identity map.
    return sessionmaker(bind=engine, future=True, expire_on_commit=True, class_=Session)


@pytest.fixture(scope="function")
def session(SessionLocal):
    with SessionLocal() as s:
        yield s

