from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import FormSchema
from eyened_orm.authz.scope import AccessScope


class FormSchemaRepository:
    """Data access for FormSchema rows."""

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def list_all(self) -> list[FormSchema]:
        """Return all form schemas, ordered by schema name ascending."""
        return list(
            self._session.scalars(
                select(FormSchema).order_by(FormSchema.SchemaName.asc())
            ).all()
        )

    def get_by_id(self, form_schema_id: int) -> FormSchema | None:
        """Return the form schema with the given id, or None if absent."""
        return self._session.get(FormSchema, form_schema_id)
