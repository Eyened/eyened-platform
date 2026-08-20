from __future__ import annotations

from eyened_orm.types import OptionalEnum


def render_optional_enum(type_, obj, autogen_context) -> str | bool:
    """Render an OptionalEnum column type as a plain ``sa.Enum``.

    ``OptionalEnum`` is a ``TypeDecorator`` whose ``impl`` is ``sa.Enum``; its
    only behaviour is on read, mapping the empty string to ``None``. The DDL it
    emits is an ordinary ENUM, so a migration should simply say ``sa.Enum``.

    Returning ``False`` defers to Alembic's own rendering.
    """
    if type_ == "type" and isinstance(obj, OptionalEnum):
        values = ", ".join(repr(v) for v in obj.enums)
        return f"sa.Enum({values}, name={obj.name!r})"
    return False
