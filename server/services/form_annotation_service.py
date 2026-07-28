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
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
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
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.images = image_repository
        self.tags = tag_repository
        self.audit = audit

    def _resolve_image_instance_id(self, image_id: str | None) -> int | None:
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
        image_instance_id = self._resolve_image_instance_id(image_id)
        return self.repository.list_active(
            patient_id=patient_id,
            study_id=study_id,
            image_instance_id=image_instance_id,
            form_schema_id=form_schema_id,
            sub_task_id=sub_task_id,
        )

    def get_annotation(self, annotation_id: int) -> FormAnnotation:
        """Return an annotation by id (with tag links loaded).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        item = self.repository.get_with_tag_links(annotation_id)
        if item is None:
            raise NotFoundError("FormAnnotation not found")
        return item

    def get_value(self, annotation_id: int) -> Any:
        """Return an annotation's raw FormData payload.

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        item = self.repository.get_by_id(annotation_id)
        if item is None:
            raise NotFoundError("FormAnnotation not found")
        return item.FormData

    def create(
        self,
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
        image_instance_id = self._resolve_image_instance_id(image_id)
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
        self.repository.add(annotation)
        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="FormAnnotation",
                actor=actor,
                entity_id=annotation.FormAnnotationID,
                changes={
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
        annotation = self.repository.get_by_id(annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        applied_columns: list[str] = []
        if "image_id" in updates:
            annotation.ImageInstanceID = self._resolve_image_instance_id(
                updates["image_id"]
            )
            applied_columns.append("ImageInstanceID")
        for key, attr in _FIELD_MAP.items():
            if key in updates:
                setattr(annotation, attr, updates[key])
                applied_columns.append(attr)

        # Derive the scalar diff (true old/new per changed PascalCase column)
        # while the mutations are still pending — before the repo flush()
        # clears the attribute history.
        changes = AuditService._diff_from_history(annotation, *applied_columns)
        self.repository.flush()
        if self.audit is not None:
            self.audit.record(
                action="UPDATE",
                entity="FormAnnotation",
                actor=actor,
                entity_id=annotation.FormAnnotationID,
                changes=changes if changes else None,
            )
        return annotation

    def soft_delete(self, annotation_id: int, actor: ActingUser) -> None:
        """Soft-delete an annotation (sets Inactive; row is kept).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(annotation_id)
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
        self.repository.flush()
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="FormAnnotation",
                actor=actor,
                entity_id=annotation_id,
                changes=deleted_data,
            )
        return None

    def set_value(
        self,
        annotation_id: int,
        form_data: Any,
        actor: ActingUser,
    ) -> None:
        """Overwrite an annotation's FormData payload (high-frequency op).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        annotation.FormData = form_data
        self.repository.flush()
        if self.audit is not None:
            # Pre-refactor log_simple carried no fields/changes (high-frequency
            # op, deliberately lightweight) — preserved as-is.
            self.audit.record(
                action="UPDATE",
                entity="FormAnnotation",
                actor=actor,
                entity_id=annotation_id,
            )
        return None

    def tag(
        self,
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
        annotation = self.repository.get_by_id(annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        tag = self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.FormAnnotation:
            raise BadRequestError("Tag type must be FormAnnotation")

        link = self.repository.get_tag_link(tag.TagID, annotation_id)
        if link is None:
            link = self.repository.add_link(
                tag_id=tag.TagID,
                form_annotation_id=annotation_id,
                creator_id=actor.id,
                comment=comment,
            )
            if self.audit is not None:
                self.audit.record(
                    action="INSERT",
                    entity="FormAnnotationTagLink",
                    actor=actor,
                    changes={
                        "tag_id": tag.TagID,
                        "form_annotation_id": annotation_id,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            link.Comment = comment
            # Derive the scalar diff while the mutation is still pending —
            # before any repo/audit call flushes (a flush clears the pending
            # history). FormAnnotationTagLink has a composite PK, so
            # entity_id is null; fold the composite identity into changes
            # (matches the INSERT branch above and untag's DELETE below), or
            # the audit row is unidentifiable.
            changes = {
                "tag_id": tag.TagID,
                "form_annotation_id": annotation_id,
                **AuditService._diff_from_history(link, "Comment"),
            }
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="FormAnnotationTagLink",
                    actor=actor,
                    changes=changes,
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def patch_tag(
        self,
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
        annotation = self.repository.get_by_id(annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        tag = self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.FormAnnotation:
            raise BadRequestError("Tag type must be FormAnnotation")

        link = self.repository.get_tag_link(tag_id, annotation_id)
        if link is None:
            raise NotFoundError("Link not found")

        if comment is not None:
            link.Comment = comment
            # Derive the scalar diff while the mutation is still pending —
            # before any repo/audit call flushes (a flush clears the pending
            # history). FormAnnotationTagLink has a composite PK, so
            # entity_id is null; fold the composite identity into changes
            # (matches tag's INSERT/UPDATE and untag's DELETE), or the audit
            # row is unidentifiable.
            changes = {
                "tag_id": tag_id,
                "form_annotation_id": annotation_id,
                **AuditService._diff_from_history(link, "Comment"),
            }
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="FormAnnotationTagLink",
                    actor=actor,
                    changes=changes,
                )

        link.Tag = tag
        return link

    def untag(
        self, annotation_id: int, tag_id: int, actor: ActingUser
    ) -> None:
        """Remove a Tag from an annotation (idempotent; no error if not linked).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")

        link = self.repository.get_tag_link(tag_id, annotation_id)
        if link is not None:
            deleted_data = {
                "tag_id": tag_id,
                "form_annotation_id": annotation_id,
                "comment": link.Comment,
                "creator_id": link.CreatorID,
            }
            self.repository.delete_link(link)
            if self.audit is not None:
                self.audit.record(
                    action="DELETE",
                    entity="FormAnnotationTagLink",
                    actor=actor,
                    changes=deleted_data,
                )
        return None


def get_form_annotation_service(
    db: Session = Depends(get_db),
) -> FormAnnotationService:
    """Default FormAnnotationService wiring for FastAPI ``Depends()``."""
    return FormAnnotationService(
        FormAnnotationRepository(db),
        ImageInstanceRepository(db),
        TagRepository(db),
        audit=get_audit_service(db),
    )
