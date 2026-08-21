"""Pool sizing is a constructor argument, not a setting.

Defaults must stay at today's values: the CLI and the five per-job Database()
constructions in server/utils/tasks.py all go through this constructor, and a
tuned default would multiply their connection count.
"""
from eyened_orm.config import DatabaseSettings
from eyened_orm.db import Database
from pydantic import SecretStr


def _settings() -> DatabaseSettings:
    # create_engine does not connect, so these need not be reachable.
    return DatabaseSettings(
        user="u", password=SecretStr("p"), host="h", database="d", port=3306
    )


def test_pool_defaults_match_todays_values():
    """An unparameterised Database keeps SQLAlchemy's 5 + 10."""
    db = Database(_settings())
    assert db.engine.pool.size() == 5
    assert db.engine.pool._max_overflow == 10


def test_pool_parameters_reach_the_engine():
    """Explicit sizing is applied, so the API can tune its own process."""
    db = Database(_settings(), pool_size=16, max_overflow=4)
    assert db.engine.pool.size() == 16
    assert db.engine.pool._max_overflow == 4


def test_pool_recycle_default():
    """An unparameterised Database keeps the 3600s default."""
    db = Database(_settings())
    assert db.engine.pool._recycle == 3600


def test_pool_recycle_parameter_reaches_engine():
    """Explicit recycle is applied, so the API can tune connection lifetime."""
    db = Database(_settings(), pool_recycle=1800)
    assert db.engine.pool._recycle == 1800
