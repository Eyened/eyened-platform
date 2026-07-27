from __future__ import annotations

from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import FormAnnotation, FormAnnotationTagLink
from eyened_orm.tag import TagType
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository

from ..db import get_db
from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import BadRequestError, NotFoundError


_FIELD_MAP = {
    "form_schema_id": "FormSchemaID",
    "patient_id": "PatientID",
    "study_id": "StudyID",
    "laterality": "Laterality",
    "sub_task_id": "SubTaskID",
    "form_data": "FormData",
    "form_annotation_reference_id": "FormAnnotationReferenceID",
}


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
        instance = self.images.get_by_public_id(image_id)
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

    def create(
        self,
        session: Session,
        *,
        form_schema_id: int,
        patient_id: int,
        study_id: int | None,
        image_id: str | None,
        laterality: Any,
        sub_task_id: int | None,
        form_data: Any,
        form_annotation_reference_id: int | None,
        actor: ActingUser,
    ) -> FormAnnotation:
        """Create a FormAnnotation owned by the acting user.

        Raises:
            NotFoundError: If image_id is given but resolves to no instance.
        """
        image_instance_id = self._resolve_image_instance_id(session, image_id)
        annotation = FormAnnotation(
            FormSchemaID=form_schema_id,
            PatientID=patient_id,
            StudyID=study_id,
            ImageInstanceID=image_instance_id,
            Laterality=laterality,
            CreatorID=actor.id,
            SubTaskID=sub_task_id,
            FormData=form_data,
            FormAnnotationReferenceID=form_annotation_reference_id,
        )
        session.add(annotation)
        session.commit()
        session.refresh(annotation)
        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint="POST /api/form-annotations",
                entity="FormAnnotation",
                entity_id=annotation.FormAnnotationID,
                fields={
                    "form_schema_id": annotation.FormSchemaID,
                    "patient_id": annotation.PatientID,
                    "study_id": annotation.StudyID,
                    "image_instance_id": annotation.ImageInstanceID,
                    "sub_task_id": annotation.SubTaskID,
                },
            )
        return annotation

    def update(
        self,
        session: Session,
        annotation_id: int,
        updates: dict[str, Any],
        actor: ActingUser,
    ) -> FormAnnotation:
        """Apply the provided (snake_case-keyed) fields to an annotation.

        ``updates`` carries only the fields the client set (the route's
        ``exclude_unset`` dict); ``image_id`` is re-resolved to an
        ImageInstanceID.

        Raises:
            NotFoundError: If the annotation, or a given image_id, is unknown.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        if "image_id" in updates:
            annotation.ImageInstanceID = self._resolve_image_instance_id(
                session, updates["image_id"]
            )
        for key, attr in _FIELD_MAP.items():
            if key in updates:
                setattr(annotation, attr, updates[key])

        session.commit()
        session.refresh(annotation)
        if self.logger is not None:
            # Decision #3: preserve the pre-refactor audit formatting quirk —
            # snake_case getattr on the ORM object always yields None, so every
            # logged change reads "None -> <new>". Behavior-preserving on
            # purpose; not an API response. A reviewer may fix separately.
            changes = {
                key: f"{getattr(annotation, key, None)} -> {value}"
                for key, value in updates.items()
            }
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/form-annotations/{annotation_id}",
                entity="FormAnnotation",
                entity_id=annotation_id,
                changes=changes if changes else None,
            )
        return annotation

    def soft_delete(
        self, session: Session, annotation_id: int, actor: ActingUser
    ) -> None:
        """Soft-delete an annotation (sets Inactive; row is kept).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        deleted_data = {
            "form_schema_id": annotation.FormSchemaID,
            "patient_id": annotation.PatientID,
            "study_id": annotation.StudyID,
            "image_instance_id": annotation.ImageInstanceID,
            "sub_task_id": annotation.SubTaskID,
            "laterality": annotation.Laterality,
            "creator_id": annotation.CreatorID,
        }
        annotation.Inactive = True
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/form-annotations/{annotation_id}",
                entity="FormAnnotation",
                entity_id=annotation_id,
                deleted_data=deleted_data,
            )
        return None

    def set_value(
        self,
        session: Session,
        annotation_id: int,
        form_data: Any,
        actor: ActingUser,
    ) -> None:
        """Overwrite an annotation's FormData payload (high-frequency op).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        annotation.FormData = form_data
        session.commit()
        if self.logger is not None:
            self.logger.log_simple(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PUT /api/form-annotations/{annotation_id}/value",
                operation="UPDATE",
                entity="FormAnnotation",
                entity_id=annotation_id,
            )
        return None

    def tag(
        self,
        session: Session,
        annotation_id: int,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> FormAnnotationTagLink:
        """Attach a Tag to an annotation (idempotent; updates comment if re-tagged).

        Raises:
            NotFoundError: If the annotation or the tag does not exist.
            BadRequestError: If the tag is not a FormAnnotation-type tag.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        tag = self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.FormAnnotation:
            raise BadRequestError("Tag type must be FormAnnotation")

        link = self.repository.get_tag_link(session, tag.TagID, annotation_id)
        if link is None:
            link = FormAnnotationTagLink(
                TagID=tag.TagID,
                FormAnnotationID=annotation_id,
                CreatorID=actor.id,
                Comment=comment,
            )
            session.add(link)
            session.commit()
            session.refresh(link)
            if self.logger is not None:
                self.logger.log_insert(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/form-annotations/{annotation_id}/tags",
                    entity="FormAnnotationTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "form_annotation_id": annotation_id,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            old_comment = link.Comment
            link.Comment = comment
            session.commit()
            session.refresh(link)
            if self.logger is not None:
                self.logger.log_update(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/form-annotations/{annotation_id}/tags",
                    entity="FormAnnotationTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "form_annotation_id": annotation_id,
                    },
                    changes={"comment": f"{old_comment} -> {comment}"},
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def patch_tag(
        self,
        session: Session,
        annotation_id: int,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> FormAnnotationTagLink:
        """Update the comment on an existing annotation tag link.

        Raises:
            NotFoundError: If the annotation, tag, or link does not exist.
            BadRequestError: If the tag is not a FormAnnotation-type tag.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        tag = self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.FormAnnotation:
            raise BadRequestError("Tag type must be FormAnnotation")

        link = self.repository.get_tag_link(session, tag_id, annotation_id)
        if link is None:
            raise NotFoundError("Link not found")

        if comment is not None:
            old_comment = link.Comment
            link.Comment = comment
            session.commit()
            session.refresh(link)
            if self.logger is not None:
                self.logger.log_update(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=(
                        f"PATCH /api/form-annotations/{annotation_id}"
                        f"/tags/{tag_id}"
                    ),
                    entity="FormAnnotationTagLink",
                    fields={
                        "tag_id": tag_id,
                        "form_annotation_id": annotation_id,
                    },
                    changes={"comment": f"{old_comment} -> {comment}"},
                )

        link.Tag = tag
        return link

    def untag(
        self, session: Session, annotation_id: int, tag_id: int, actor: ActingUser
    ) -> None:
        """Remove a Tag from an annotation (idempotent; no error if not linked).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(session, annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        link = self.repository.get_tag_link(session, tag_id, annotation_id)
        if link is not None:
            deleted_data = {
                "tag_id": tag_id,
                "form_annotation_id": annotation_id,
                "comment": link.Comment,
                "creator_id": link.CreatorID,
            }
            session.delete(link)
            session.commit()
            if self.logger is not None:
                self.logger.log_delete(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=(
                        f"DELETE /api/form-annotations/{annotation_id}"
                        f"/tags/{tag_id}"
                    ),
                    entity="FormAnnotationTagLink",
                    fields={"tag_id": tag_id, "form_annotation_id": annotation_id},
                    deleted_data=deleted_data,
                )
        return None


def get_form_annotation_service(
    db: Session = Depends(get_db),
) -> FormAnnotationService:
    """Default FormAnnotationService wiring for FastAPI ``Depends()``."""
    return FormAnnotationService(
        FormAnnotationRepository(),
        ImageInstanceRepository(db),
        TagRepository(db),
        logger=get_db_logger(),
    )
