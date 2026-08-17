"""The Alembic revision graph must stay linear.

A forked graph makes `alembic upgrade head` ambiguous and silently breaks the
schema-sync CI job, which upgrades to a single head.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "migrations" / "alembic"


def test_migration_chain_has_single_head():
    """The repo's revision chain resolves to exactly one head."""
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    heads = ScriptDirectory.from_config(config).get_heads()

    assert len(heads) == 1, f"expected a single head, found {heads}"
