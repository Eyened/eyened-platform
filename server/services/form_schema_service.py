from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import FormSchema
from eyened_orm.repositories.form_schema_repository import FormSchemaRepository

from ..db import get_db
from .exceptions import NotFoundError


class FormSchemaService:
    """Business logic for form schemas."""

    def __init__(self, repository: FormSchemaRepository) -> None:
        self.repository = repository

    def list_form_schemas(self) -> list[FormSchema]:
        """Return all form schemas, ordered by schema name."""
        return self.repository.list_all()

    def get_form_schema(self, form_schema_id: int) -> FormSchema:
        """Return the form schema with the given id.

        Raises:
            NotFoundError: If no form schema with ``form_schema_id`` exists.
        """
        schema = self.repository.get_by_id(form_schema_id)
        if schema is None:
            raise NotFoundError(f"FormSchema {form_schema_id} not found")
        return schema


def get_form_schema_service(db: Session = Depends(get_db)) -> FormSchemaService:
    """Default FormSchemaService wiring for FastAPI ``Depends()``."""
    return FormSchemaService(FormSchemaRepository(db))
