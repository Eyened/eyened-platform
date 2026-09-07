"""Autogenerate must emit runnable code for OptionalEnum columns.

Left to itself Alembic renders eyened_orm.types.OptionalEnum(<values>), which
fails twice: the generated module never imports eyened_orm, and the constructor
takes an enum class rather than a list of values.
"""

import sqlalchemy as sa

from eyened_orm.base import Base
from eyened_orm.types import CurrentTimestampOnUpdate
from eyened_orm.utils.alembic_render import render_custom_item


def test_renders_both_custom_constructs_and_defers_otherwise():
    """Autogenerate renders migration files against the *generic* dialect, so
    CurrentTimestampOnUpdate compiles there to a bare CURRENT_TIMESTAMP: left
    alone, regenerating the baseline drops the ON UPDATE half and writes the
    original bug back, invisibly. OptionalEnum is checked in the same test
    because one hook now serves both -- configure() takes a single callable --
    and losing either would fail silently.
    """
    sex = Base.metadata.tables["Patient"].columns["Sex"].type
    assert render_custom_item("type", sex, None) == "sa.Enum('M', 'F', name='sexenum')"

    # What Alembic hands the hook is the DefaultClause wrapping the construct,
    # not the construct: an isinstance check against the latter never fires.
    default = sa.Column("s", sa.DateTime(), server_default=CurrentTimestampOnUpdate()).server_default
    assert render_custom_item("server_default", default, None) == (
        "sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')"
    )

    assert render_custom_item("type", sa.Integer(), None) is False
