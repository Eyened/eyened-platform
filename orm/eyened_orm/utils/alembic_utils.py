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


def upgrade_to_head(engine: Engine) -> str:
    """Run the migration trail to head against ``engine``'s database.

    The connection goes through ``config.attributes`` so ``env.py`` skips its
    confirmation prompt -- the caller has already confirmed the target. A bare
    ``Config()`` is deliberate: passing ``alembic.ini`` would set
    ``config_file_name`` and make ``env.py`` reconfigure global logging.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(_migrations_dir() / "alembic"))

    with engine.connect() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")

    head = _script_directory().get_current_head()
    if head is None:
        raise RuntimeError("No Alembic head revision found.")
    return head
