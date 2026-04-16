from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.compiler import compiles
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.sql.sqltypes import BLOB, JSON
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _install_sqlite_type_shims() -> None:
    """
    The ORM targets MySQL/MariaDB and uses MySQL-only types in a few models.
    For in-memory SQLite unit tests we compile these types into compatible
    SQLite types so Base.metadata.create_all() can build the full schema.
    """

    @compiles(LONGBLOB, "sqlite")
    def _compile_longblob_sqlite(element, compiler, **kw):  # noqa: ANN001
        return compiler.visit_BLOB(BLOB(), **kw)

    # Some models import MySQL JSON; SQLite supports JSON as TEXT-ish,
    # but compilation can vary by dialect/type class. Normalize to generic JSON.
    @compiles(MySQLJSON, "sqlite")
    def _compile_mysqljson_sqlite(element, compiler, **kw):  # noqa: ANN001
        return compiler.process(JSON(), **kw)


@pytest.fixture(scope="function")
def engine():
    """
    In-memory SQLite engine with a StaticPool so all sessions in a test share
    the same database connection.
    """
    repo_root = Path(__file__).resolve().parents[2]
    orm_root = repo_root / "orm"
    if str(orm_root) not in sys.path:
        sys.path.insert(0, str(orm_root))

    # Importing the package registers all ORM models on Base.metadata.
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


@pytest.fixture(scope="function")
def SessionLocal(engine):
    return sessionmaker(bind=engine, future=True, expire_on_commit=False, class_=Session)


@pytest.fixture(scope="function")
def session(SessionLocal):
    with SessionLocal() as s:
        yield s
