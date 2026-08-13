from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, with_loader_criteria

from eyened_orm import (
    FormAnnotation,
    FormAnnotationTagLink,
    ImageInstance,
    ImageInstanceTagLink,
    Patient,
    Study,
    StudyTagLink,
    SubTask,
)
from eyened_orm.authz.scope import AccessScope
from eyened_orm.authz.scoping import apply_scope, projects_of, scope_criteria
from eyened_orm.repositories._scoped import scoped_one


class FormAnnotationRepository:
    """Data access for FormAnnotation reads, mutations, and its Tag links."""

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def project_ids(self, annotation_id: int) -> set[int]:
        """The projects this annotation touches, for a write check to be judged on.

        The repository owns the Session, so the authz resolution runs here
        rather than a service reaching through for a Session it must not hold.
        Uses ``projects_of``, the one definition the reads and the CLI share.

        Deliberately unscoped: the returned set is the *input* to
        ``AccessScope.require``, so filtering it by the caller's scope would
        remove exactly the projects the check exists to catch and make every
        floor pass.
        """
        return projects_of(self._session, FormAnnotation, annotation_id)

    def project_ids_of_patient(self, patient_id: int) -> set[int]:
        """The project a patient sits in, for the floor on *creating* an
        annotation -- which has no row of its own to resolve yet.

        Lives here rather than on a ``PatientRepository`` for the same reason
        ``SubTaskRepository.project_ids_of_image`` lives beside its only caller:
        ``FormAnnotation`` is anchored to ``Patient``, and this repository is
        the one the create path already holds. Deliberately unscoped, as above.
        """
        return projects_of(self._session, Patient, patient_id)

    def get_study(self, study_id: int) -> Study | None:
        """Return the study by id, or None if absent or out of scope.

        Here rather than on ``StudyRepository`` for the same reason
        ``project_ids_of_patient`` is: an annotation's ``StudyID`` is written by
        the create/update path, and this is the repository that path already
        holds. What it returns is unused -- ``None`` is the whole answer, and
        it means "you cannot point an annotation at this", indistinguishable
        from "it does not exist" by design.
        """
        return scoped_one(
            self._session, Study, self._scope, Study.StudyID == study_id
        )

    def get_subtask(self, subtask_id: int) -> SubTask | None:
        """Return the subtask by id, or None if absent or out of scope.

        A ``SubTask`` is scoped by its parent task's whole project set, so this
        answers "may this caller file an annotation under that subtask" with
        the same rule that decides whether they can see the task at all.
        """
        return scoped_one(
            self._session, SubTask, self._scope, SubTask.SubTaskID == subtask_id
        )

    def _scoped_image_options(self) -> tuple:
        """Eager-load ``ImageInstance`` under the scope, so an out-of-reach one
        arrives loaded and **None** rather than lazily resolving later.

        A ``FormAnnotation`` is anchored on ``PatientID``; the image it names has
        its own, different anchor, so a row whose two anchors disagree is
        legitimately readable by a caller who cannot see the image. Left
        unloaded, the DTO's ``getattr(annotation.ImageInstance, "PublicID")``
        lazy-loads it with no scope in the chain and emits the PublicID of an
        image in a project the caller holds nothing in.

        Eager-loading is not incidental here: ``form_annotation_to_get`` decides
        whether an absent image means "withheld" or "resolve it from the raw
        Session" by asking whether the relationship is loaded. An unloaded
        relationship takes the fallback and re-discloses exactly what this
        withholds, so the ``selectinload`` must be present whenever the criteria
        are -- the two are one option set, deliberately built together.

        ``scope_criteria`` returns None for an administrator (and for an
        unfiltered entity), where a tautology would read as a filter that is in
        force. Same predicate as ``apply_scope`` puts on an ImageInstance read,
        via the same registry walk -- not a second hand-written rule.
        """
        options: list = [selectinload(FormAnnotation.ImageInstance)]
        criteria = scope_criteria(ImageInstance, self._scope)
        if criteria is not None:
            options.append(with_loader_criteria(ImageInstance, criteria))
        return tuple(options)

    def get_by_id(self, annotation_id: int) -> FormAnnotation | None:
        """Return the annotation by id, or None if absent or out of scope.

        The image is eager-loaded under the scope because this is the read the
        **update** path returns, and the route converts what it returns
        straight into the response. The other callers here ignore the
        relationship; one selectin query is the price of the two response paths
        not disagreeing with the listing about the same row.
        """
        return scoped_one(
            self._session,
            FormAnnotation,
            self._scope,
            FormAnnotation.FormAnnotationID == annotation_id,
            options=self._scoped_image_options(),
        )

    def get_with_tag_links(self, annotation_id: int) -> FormAnnotation | None:
        """Return the annotation by id with its tag links loaded, or None if
        absent or out of scope."""
        return scoped_one(
            self._session,
            FormAnnotation,
            self._scope,
            FormAnnotation.FormAnnotationID == annotation_id,
            options=(
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Tag),
                selectinload(
                    FormAnnotation.FormAnnotationTagLinks
                ).selectinload(FormAnnotationTagLink.Creator),
                *self._scoped_image_options(),
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
        # The annotation is anchored on PatientID; the image it names has its
        # own, different anchor, and a selectinload issues its own SELECT that
        # the root's WHERE never reaches. Without this, a caller entitled to a
        # mis-scoped annotation is handed the PublicID of an image in a project
        # they hold nothing in. Same predicate as the root, via the same
        # registry walk -- not a second hand-written rule.
        image_criteria = scope_criteria(ImageInstance, self._scope)
        if image_criteria is not None:
            query = query.options(with_loader_criteria(ImageInstance, image_criteria))
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
        query = apply_scope(query, FormAnnotation, self._scope)
        return list(self._session.scalars(query).all())

    def get_tag_link(
        self, tag_id: int, annotation_id: int
    ) -> FormAnnotationTagLink | None:
        """Return the link for (tag_id, annotation_id), or None if absent or
        out of scope."""
        return scoped_one(
            self._session,
            FormAnnotationTagLink,
            self._scope,
            FormAnnotationTagLink.TagID == tag_id,
            FormAnnotationTagLink.FormAnnotationID == annotation_id,
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
