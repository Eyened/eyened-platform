"""The Alembic revision graph must stay linear.

A forked graph makes `alembic upgrade head` ambiguous and silently breaks the
schema-sync CI job, which upgrades to a single head.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
ALEMBIC_INI = MIGRATIONS_DIR / "alembic.ini"
ALEMBIC_DIR = MIGRATIONS_DIR / "alembic"


def test_migration_chain_has_single_head():
    """The repo's revision chain resolves to exactly one head.

    Reads the real alembic.ini, not a stand-in, so that adding version_locations
    or recursive_version_locations there -- which would expose versions_archive/
    -- is caught here. prepend_sys_path is cleared because from_config acts on it.
    """
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    config.set_main_option("prepend_sys_path", "")
    heads = ScriptDirectory.from_config(config).get_heads()

    assert len(heads) == 1, f"expected a single head, found {heads}"
