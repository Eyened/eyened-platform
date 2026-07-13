from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from eyened_orm import FormAnnotation
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .exceptions import NotFoundError


class FormAnnotationService:
    """Business logic for FormAnnotation CRUD, values, and Tag links."""

    def __init__(
        self,
        repository: FormAnnotationRepository,
        image_repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.images = image_repository
        self.tags = tag_repository
        self.logger = logger

    def _resolve_image_instance_id(
        self, session: Session, image_id: str | None
    ) -> int | None:
        """Map a PublicID to its ImageInstanceID (None passes through).

        Raises:
            NotFoundError: If a non-None image_id resolves to no instance.
        """
        if image_id is None:
            return None
        instance = self.images.get_by_public_id(session, image_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        return instance.ImageInstanceID

    def list_annotations(
        self,
        session: Session,
        *,
        patient_id: int | None,
        study_id: int | None,
        image_id: str | None,
        form_schema_id: int | None,
        sub_task_id: int | None,
    ) -> list[FormAnnotation]:
        """List active annotations matching the filters (resolving image_id).

        Raises:
            NotFoundError: If image_id is given but resolves to no instance.
        """
        image_instance_id = self._resolve_image_instance_id(session, image_id)
        return self.repository.list_active(
            session,
            patient_id=patient_id,
            study_id=study_id,
            image_instance_id=image_instance_id,
            form_schema_id=form_schema_id,
            sub_task_id=sub_task_id,
        )

    def get_annotation(
        self, session: Session, annotation_id: int
    ) -> FormAnnotation:
        """Return an annotation by id (with tag links loaded).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        item = self.repository.get_with_tag_links(session, annotation_id)
        if item is None:
            raise NotFoundError("FormAnnotation not found")
        return item

    def get_value(self, session: Session, annotation_id: int) -> Any:
        """Return an annotation's raw FormData payload.

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        item = self.repository.get_by_id(session, annotation_id)
        if item is None:
            raise NotFoundError("FormAnnotation not found")
        return item.FormData


def get_form_annotation_service() -> FormAnnotationService:
    """Default FormAnnotationService wiring for FastAPI ``Depends()``."""
    return FormAnnotationService(
        FormAnnotationRepository(),
        ImageInstanceRepository(),
        TagRepository(),
        logger=get_db_logger(),
    )
