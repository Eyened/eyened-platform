from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "migrations"


def _script_directory():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    migrations_dir = _migrations_dir()
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir / "alembic"))
    return ScriptDirectory.from_config(cfg)


def get_current_alembic_revision(engine: Engine) -> str | None:
    if "alembic_version" not in inspect(engine).get_table_names():
        return None
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def stamp_alembic_head(engine: Engine) -> str:
    from alembic.runtime.migration import MigrationContext

    script = _script_directory()
    head = script.get_current_head()
    if head is None:
        raise RuntimeError("No Alembic head revision found.")

    current = get_current_alembic_revision(engine)
    if current == head:
        return head

    with engine.begin() as connection:
        context = MigrationContext.configure(connection=connection)
        context.stamp(script, head)

    return head
