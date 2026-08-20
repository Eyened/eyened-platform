from __future__ import annotations

from eyened_orm.types import OptionalEnum


def render_optional_enum(type_, obj, autogen_context) -> str | bool:
    """Render an OptionalEnum column type as a plain ``sa.Enum``.

    OptionalEnum is a ``TypeDecorator`` over ``sa.Enum`` and emits ordinary ENUM
    DDL. Returns ``False`` to defer to Alembic's own rendering.
    """
    if type_ == "type" and isinstance(obj, OptionalEnum):
        values = ", ".join(repr(v) for v in obj.enums)
        return f"sa.Enum({values}, name={obj.name!r})"
    return False
