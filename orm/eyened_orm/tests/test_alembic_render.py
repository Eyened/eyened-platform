"""Autogenerate must emit runnable code for OptionalEnum columns.

Left to itself Alembic renders eyened_orm.types.OptionalEnum(<values>), which
fails twice: the generated module never imports eyened_orm, and the constructor
takes an enum class rather than a list of values.
"""

import sqlalchemy as sa

from eyened_orm.base import Base
from eyened_orm.utils.alembic_render import render_optional_enum


def test_renders_optional_enum_as_plain_sa_enum():
    """A real OptionalEnum column renders as sa.Enum with its values and name."""
    sex = Base.metadata.tables["Patient"].columns["Sex"].type
    assert render_optional_enum("type", sex, None) == "sa.Enum('M', 'F', name='sexenum')"


def test_defers_to_alembic_for_other_types():
    """Returning False leaves every other column to Alembic's own rendering."""
    assert render_optional_enum("type", sa.Integer(), None) is False
