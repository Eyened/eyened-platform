from __future__ import annotations

from eyened_orm.types import CurrentTimestampOnUpdate, OptionalEnum


def render_custom_item(type_, obj, autogen_context) -> str | bool:
    """Render this ORM's custom SQL constructs into migration files.

    OptionalEnum is a ``TypeDecorator`` over ``sa.Enum`` and emits ordinary
    ENUM DDL, but Alembic would render the decorator itself -- code the
    generated module cannot run.

    CurrentTimestampOnUpdate compiles to a bare CURRENT_TIMESTAMP under the
    generic dialect autogenerate uses, so without this the ON UPDATE half is
    dropped from every generated migration. ``obj`` is the ``DefaultClause``
    wrapping the construct, not the construct.

    ``False`` defers to Alembic's own rendering.
    """
    if type_ == "type" and isinstance(obj, OptionalEnum):
        values = ", ".join(repr(v) for v in obj.enums)
        return f"sa.Enum({values}, name={obj.name!r})"
    if type_ == "server_default" and isinstance(
        getattr(obj, "arg", None), CurrentTimestampOnUpdate
    ):
        return "sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')"
    return False
