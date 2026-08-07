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
from eyened_orm.authz.scope import AccessScope


class FormAnnotationRepository:
    """Data access for FormAnnotation reads, mutations, and its Tag links."""

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def get_by_id(self, annotation_id: int) -> FormAnnotation | None:
        """Return the annotation by id, or None if absent."""
        return self._session.get(FormAnnotation, annotation_id)

    def get_with_tag_links(self, annotation_id: int) -> FormAnnotation | None:
        """Return the annotation by id with its tag links loaded, or None."""
        return self._session.get(
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
        return list(self._session.scalars(query).all())

    def get_tag_link(
        self, tag_id: int, annotation_id: int
    ) -> FormAnnotationTagLink | None:
        """Return the link for (tag_id, annotation_id), or None if absent."""
        return self._session.get(
            FormAnnotationTagLink,
            {"TagID": tag_id, "FormAnnotationID": annotation_id},
        )

    def add(self, annotation: FormAnnotation) -> None:
        """Stage a new FormAnnotation and flush so its PK/server defaults populate."""
        self._session.add(annotation)
        self._session.flush()

    def save(self, annotation: FormAnnotation) -> None:
        """Persist in-place mutations to ``annotation`` (e.g. ``Inactive``,
        ``FormData``) within the request transaction, so the ``onupdate`` column
        ``DateModified`` is re-fetched before the response is serialized.

        ``annotation`` names what is being saved; the flush covers the whole
        unit of work, deliberately not just this row.
        """
        self._session.flush()

    def add_link(
        self,
        *,
        tag_id: int,
        form_annotation_id: int,
        creator_id: int,
        comment: str | None,
    ) -> FormAnnotationTagLink:
        """Create a FormAnnotationTagLink and flush so its row (and PK) is written."""
        link = FormAnnotationTagLink(
            TagID=tag_id,
            FormAnnotationID=form_annotation_id,
            CreatorID=creator_id,
            Comment=comment,
        )
        self._session.add(link)
        self._session.flush()
        return link

    def save_link(self, link: FormAnnotationTagLink) -> None:
        """Persist in-place mutations to ``link`` (e.g. ``Comment``) within the
        request transaction.

        ``link`` names what is being saved; the flush covers the whole unit of
        work, deliberately not just this row.
        """
        self._session.flush()

    def delete_link(self, link: FormAnnotationTagLink) -> None:
        """Delete a FormAnnotationTagLink and flush within the request transaction."""
        self._session.delete(link)
        self._session.flush()
