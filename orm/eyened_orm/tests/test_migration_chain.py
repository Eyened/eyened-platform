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

    Loads the real alembic.ini rather than a bare Config: its
    version_locations / recursive_version_locations settings are what keep
    versions_archive/ (the 24 archived legacy revisions) invisible to
    Alembic, so the guard has to read the file that actually decides that,
    not a stand-in that could never see an edit there. This doesn't run
    env.py -- ScriptDirectory.from_config only reads the ini, it never
    invokes the migration environment -- so it's safe unlike the bare
    Config() in upgrade_to_head().
    """
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    heads = ScriptDirectory.from_config(config).get_heads()

    assert len(heads) == 1, f"expected a single head, found {heads}"
