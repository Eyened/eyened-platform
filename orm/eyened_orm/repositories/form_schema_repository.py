from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import FormSchema


class FormSchemaRepository:
    """Data access for FormSchema rows."""

    def list_all(self, session: Session) -> list[FormSchema]:
        """Return all form schemas, ordered by schema name ascending."""
        return list(
            session.scalars(
                select(FormSchema).order_by(FormSchema.SchemaName.asc())
            ).all()
        )

    def get_by_id(self, session: Session, form_schema_id: int) -> FormSchema | None:
        """Return the form schema with the given id, or None if absent."""
        return session.get(FormSchema, form_schema_id)
