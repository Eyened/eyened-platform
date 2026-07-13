from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from eyened_orm import (
    FormAnnotation,
    FormAnnotationTagLink,
    ImageInstance,
    ImageInstanceTagLink,
    Study,
    StudyTagLink,
)


class FormAnnotationRepository:
    """Data access for FormAnnotation reads and its Tag links."""

    def get_by_id(
        self, session: Session, annotation_id: int
    ) -> FormAnnotation | None:
        """Return the annotation by id, or None if absent."""
        return session.get(FormAnnotation, annotation_id)

    def get_with_tag_links(
        self, session: Session, annotation_id: int
    ) -> FormAnnotation | None:
        """Return the annotation by id with its tag links loaded, or None."""
        return session.get(
            FormAnnotation,
            annotation_id,
            options=(
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Tag),
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Creator),
            ),
        )

    def list_active(
        self,
        session: Session,
        *,
        patient_id: int | None = None,
        study_id: int | None = None,
        image_instance_id: int | None = None,
        form_schema_id: int | None = None,
        sub_task_id: int | None = None,
    ) -> list[FormAnnotation]:
        """Return active (``~Inactive``) annotations matching the given filters.

        Mirrors the eager-load graph the ``GET /form-annotations`` handler
        built inline. ``image_instance_id`` is already resolved from a
        PublicID by the Service; ``None`` filters are not applied.
        """
        query = (
            select(FormAnnotation)
            .filter(~FormAnnotation.Inactive)
            .options(
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Tag),
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Creator),
                selectinload(FormAnnotation.Study)
                .selectinload(Study.StudyTagLinks)
                .selectinload(StudyTagLink.Tag),
                selectinload(FormAnnotation.Study)
                .selectinload(Study.StudyTagLinks)
                .selectinload(StudyTagLink.Creator),
                selectinload(FormAnnotation.ImageInstance)
                .selectinload(ImageInstance.ImageInstanceTagLinks)
                .selectinload(ImageInstanceTagLink.Tag),
                selectinload(FormAnnotation.ImageInstance)
                .selectinload(ImageInstance.ImageInstanceTagLinks)
                .selectinload(ImageInstanceTagLink.Creator),
            )
        )
        if patient_id is not None:
            query = query.filter(FormAnnotation.PatientID == patient_id)
        if study_id is not None:
            query = query.filter(FormAnnotation.StudyID == study_id)
        if image_instance_id is not None:
            query = query.filter(
                FormAnnotation.ImageInstanceID == image_instance_id
            )
        if form_schema_id is not None:
            query = query.filter(FormAnnotation.FormSchemaID == form_schema_id)
        if sub_task_id is not None:
            query = query.filter(FormAnnotation.SubTaskID == sub_task_id)
        return list(session.scalars(query).all())

    def get_tag_link(
        self, session: Session, tag_id: int, annotation_id: int
    ) -> FormAnnotationTagLink | None:
        """Return the link for (tag_id, annotation_id), or None if absent."""
        return session.get(
            FormAnnotationTagLink,
            {"TagID": tag_id, "FormAnnotationID": annotation_id},
        )
