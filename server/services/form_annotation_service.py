from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
from eyened_orm.repositories.task_repository import SubTaskRepository
from eyened_orm.authz.ownership import require_owner, require_owner_or_project_admin
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope

from ..db import get_db
from .access_scope import get_access_scope
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import BadRequestError, NotFoundError

if TYPE_CHECKING:
    from eyened_orm import ImageInstance


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
        subtask_repository: SubTaskRepository,
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.images = image_repository
        self.tags = tag_repository
        self.subtasks = subtask_repository
        self.scope = scope
        self._actor = ActingUser.from_scope(scope)
        self.audit = audit

    def _resolve_image_instance(self, image_id: str | None) -> ImageInstance | None:
        """Map a PublicID to its ImageInstance (None passes through).

        Returns the row rather than its id so the write paths can assign the
        **relationship**, not just the FK: the response DTO reads an image id
        only off a loaded relationship, and this lookup is scoped, so the object
        it returns is one the caller is entitled to name.

        Raises:
            NotFoundError: If a non-None image_id resolves to no instance.
        """
        if image_id is None:
            return None
        instance = self.images.get_by_public_id(image_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        return instance

    def _resolve_image_instance_id(self, image_id: str | None) -> int | None:
        """Map a PublicID to its ImageInstanceID (None passes through).

        Raises:
            NotFoundError: If a non-None image_id resolves to no instance.
        """
        instance = self._resolve_image_instance(image_id)
        return instance.ImageInstanceID if instance is not None else None

    def _require_reachable_references(self, values: dict[str, Any]) -> None:
        """Refuse an id the caller cannot reach, before it is written.

        ``values`` carries only the reference fields present on this call
        (``None`` is a legitimate value meaning "clear it", so it passes). Each
        id is resolved through a **scoped** lookup, which is what ``image_id``
        has always done -- an id outside the caller's reach comes back as
        ``None`` and is answered exactly as a non-existent one is. Without this
        a grader could file an annotation under another project's study or
        subtask, or cite its annotation as a reference; that is an
        unauthorized write, and it is how a row whose anchors disagree gets
        made in the first place.

        Not a consistency guard: nothing here asks whether the study belongs to
        the patient. That question was deliberately left open.
        """
        study_id = values.get("study_id")
        if study_id is not None and self.repository.get_study(study_id) is None:
            raise NotFoundError("Study not found")

        sub_task_id = values.get("sub_task_id")
        if sub_task_id is not None and self.repository.get_subtask(sub_task_id) is None:
            raise NotFoundError("SubTask not found")

        reference_id = values.get("form_annotation_reference_id")
        if reference_id is not None and self.repository.get_by_id(reference_id) is None:
            raise NotFoundError("Referenced FormAnnotation not found")

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
        # Opts into the scoped image load: this is the read behind
        # ``GET /form-annotations/{id}``, whose response carries ``image_id``.
        item = self.repository.get_with_tag_links(annotation_id, with_image=True)
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
    ) -> FormAnnotation:
        """Create a FormAnnotation owned by the acting user.

        Raises:
            NotFoundError: If image_id is given but resolves to no instance.
        """
        image = self._resolve_image_instance(image_id)
        self._require_reachable_references(
            {
                "study_id": study_id,
                "sub_task_id": sub_task_id,
                "form_annotation_reference_id": form_annotation_reference_id,
            }
        )
        # No ownership overlay on create: the row does not exist yet and its
        # author is the caller by construction (CreatorID below). The floor is
        # judged on the patient's project -- ``FormAnnotation``'s own anchor --
        # because there is no annotation row to resolve projects from yet.
        self.scope.require(
            self.repository.project_ids_of_patient(patient_id),
            ProjectRole.grader,
            entity="FormAnnotation",
            entity_id=None,
        )
        annotation = FormAnnotation(
            FormSchemaID=form_schema_id,
            PatientID=patient_id,
            StudyID=study_id,
            ImageInstanceID=image.ImageInstanceID if image is not None else None,
            Laterality=laterality,
            CreatorID=self.scope.actor_id,
            SubTaskID=sub_task_id,
            FormData=form_data,
            FormAnnotationReferenceID=form_annotation_reference_id,
        )
        # The create response is serialised from this object, and the DTO reads
        # an image id only off a loaded relationship. Assigning the row the
        # scoped lookup already returned is how the create path opts in -- no
        # second read, and nothing here can name an image the resolution above
        # refused. ``None`` is assigned too: loaded-and-empty, not unasked.
        annotation.ImageInstance = image
        self.repository.add(annotation)
        if sub_task_id is not None:
            self.subtasks.claim_if_unassigned(sub_task_id, self.scope.actor_id)
        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="FormAnnotation",
                actor=self._actor,
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
    ) -> FormAnnotation:
        """Apply the provided (snake_case-keyed) fields to an annotation.

        ``updates`` carries only the fields the client set (the route's
        ``exclude_unset`` dict); ``image_id`` is re-resolved to an
        ImageInstanceID.

        Raises:
            NotFoundError: If the annotation, or a given image_id, is unknown.
        """
        # Opts into the scoped image load: the route converts what this returns
        # straight into the PATCH response, so it is a response read whether or
        # not the image was touched.
        annotation = self.repository.get_by_id(annotation_id, with_image=True)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        projects = self.repository.project_ids(annotation_id)
        # ``patient_id`` re-anchors the row: a FormAnnotation's project is its
        # patient's, so this write is as much *into* the destination project as
        # out of the current one. Judged on the union of before and after --
        # the shape ``SubTaskService.add_image`` uses, and the same destination
        # check ``create`` makes above. Without the second half a grader in one
        # project could push their annotation into a project they hold nothing
        # in, where it reads as legitimate data and its own project_admin can
        # no longer reach it.
        projects_after = (
            self.repository.project_ids_of_patient(updates["patient_id"])
            if "patient_id" in updates
            else set()
        )
        self.scope.require(
            projects | projects_after,
            ProjectRole.grader,
            entity="FormAnnotation",
            entity_id=annotation_id,
        )
        require_owner(
            self.scope,
            owner_id=annotation.CreatorID,
            entity="FormAnnotation",
            entity_id=annotation_id,
            projects=projects,
        )

        # After the floor and the overlay, not before: the caller must be
        # entitled to modify this row before the request body is judged at all.
        self._require_reachable_references(updates)

        # Column list is purely updates-key-driven, so it can be built before
        # any mutation happens -- which is what snapshot() requires.
        applied_columns: list[str] = (
            ["ImageInstanceID"] if "image_id" in updates else []
        ) + [attr for key, attr in _FIELD_MAP.items() if key in updates]
        before = AuditService.snapshot(annotation, *applied_columns)

        if "image_id" in updates:
            # Both halves, deliberately. The FK is what the audit diff reads
            # (it runs before the flush that would sync it from the
            # relationship), and the relationship is what the response DTO
            # reads -- ``get_by_id(with_image=True)`` above left it loaded with
            # the *old* image, and a flush does not expire it, so setting only
            # the FK would answer the PATCH with the id of the image that was
            # just replaced.
            image = self._resolve_image_instance(updates["image_id"])
            annotation.ImageInstanceID = (
                image.ImageInstanceID if image is not None else None
            )
            annotation.ImageInstance = image
        for key, attr in _FIELD_MAP.items():
            if key in updates:
                setattr(annotation, attr, updates[key])

        changes = AuditService.diff(before, annotation)
        self.repository.save(annotation)
        if self.audit is not None:
            self.audit.record(
                action="UPDATE",
                entity="FormAnnotation",
                actor=self._actor,
                entity_id=annotation.FormAnnotationID,
                changes=changes if changes else None,
            )
        return annotation

    def soft_delete(self, annotation_id: int) -> None:
        """Soft-delete an annotation (sets Inactive; row is kept).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        projects = self.repository.project_ids(annotation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="FormAnnotation",
            entity_id=annotation_id,
        )
        require_owner_or_project_admin(
            self.scope,
            owner_id=annotation.CreatorID,
            entity="FormAnnotation",
            entity_id=annotation_id,
            projects=projects,
        )

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
        self.repository.save(annotation)
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="FormAnnotation",
                actor=self._actor,
                entity_id=annotation_id,
                changes=deleted_data,
            )
        return None

    def set_value(
        self,
        annotation_id: int,
        form_data: Any,
    ) -> None:
        """Overwrite an annotation's FormData payload (high-frequency op).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        projects = self.repository.project_ids(annotation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="FormAnnotation",
            entity_id=annotation_id,
        )
        require_owner(
            self.scope,
            owner_id=annotation.CreatorID,
            entity="FormAnnotation",
            entity_id=annotation_id,
            projects=projects,
        )

        annotation.FormData = form_data
        self.repository.save(annotation)
        if self.audit is not None:
            # Pre-refactor log_simple carried no fields/changes (high-frequency
            # op, deliberately lightweight) — preserved as-is.
            self.audit.record(
                action="UPDATE",
                entity="FormAnnotation",
                actor=self._actor,
                entity_id=annotation_id,
            )
        return None

    def tag(
        self,
        annotation_id: int,
        tag_id: int,
        comment: str | None,
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
        # A tag link carries no project of its own, so it is authorized against
        # its *parent* -- the deliberate asymmetry recorded at ``PROJECT_IDS_OF``
        # (``projects_of(session, FormAnnotationTagLink, ...)`` raises by
        # design). The floor therefore names the parent, whose projects it is
        # judged on; the ownership overlay names the link, whose CreatorID it
        # reads, with ``entity_id=None`` because a link's key is composite.
        projects = self.repository.project_ids(annotation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="FormAnnotation",
            entity_id=annotation_id,
        )

        link = self.repository.get_tag_link(tag.TagID, annotation_id)
        if link is None:
            link = self.repository.add_link(
                tag_id=tag.TagID,
                form_annotation_id=annotation_id,
                creator_id=self.scope.actor_id,
                comment=comment,
            )
            if self.audit is not None:
                self.audit.record(
                    action="INSERT",
                    entity="FormAnnotationTagLink",
                    actor=self._actor,
                    changes={
                        "tag_id": tag.TagID,
                        "form_annotation_id": annotation_id,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            # This branch overwrites an existing link's comment, so it is a
            # modify and takes the same overlay ``patch_tag`` does. Without it
            # POST would be a standing bypass of PATCH's ownership check.
            require_owner(
                self.scope,
                owner_id=link.CreatorID,
                entity="FormAnnotationTagLink",
                entity_id=None,
                projects=projects,
            )
            before = AuditService.snapshot(link, "Comment")
            link.Comment = comment
            # FormAnnotationTagLink has a composite PK, so entity_id is null;
            # fold the composite identity into changes (matches the INSERT
            # branch above and untag's DELETE below), or the audit row is
            # unidentifiable.
            changes = {
                "tag_id": tag.TagID,
                "form_annotation_id": annotation_id,
                **AuditService.diff(before, link),
            }
            self.repository.save_link(link)
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="FormAnnotationTagLink",
                    actor=self._actor,
                    changes=changes,
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def patch_tag(
        self,
        annotation_id: int,
        tag_id: int,
        comment: str | None,
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
        projects = self.repository.project_ids(annotation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="FormAnnotation",
            entity_id=annotation_id,
        )

        link = self.repository.get_tag_link(tag_id, annotation_id)
        if link is None:
            raise NotFoundError("Link not found")
        require_owner(
            self.scope,
            owner_id=link.CreatorID,
            entity="FormAnnotationTagLink",
            entity_id=None,
            projects=projects,
        )

        if comment is not None:
            before = AuditService.snapshot(link, "Comment")
            link.Comment = comment
            # FormAnnotationTagLink has a composite PK, so entity_id is null;
            # fold the composite identity into changes (matches tag's
            # INSERT/UPDATE and untag's DELETE), or the audit row is
            # unidentifiable.
            changes = {
                "tag_id": tag_id,
                "form_annotation_id": annotation_id,
                **AuditService.diff(before, link),
            }
            self.repository.save_link(link)
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="FormAnnotationTagLink",
                    actor=self._actor,
                    changes=changes,
                )

        link.Tag = tag
        return link

    def untag(self, annotation_id: int, tag_id: int) -> None:
        """Remove a Tag from an annotation (idempotent; no error if not linked).

        Raises:
            NotFoundError: If the annotation does not exist.
        """
        annotation = self.repository.get_by_id(annotation_id)
        if annotation is None:
            raise NotFoundError("FormAnnotation not found")
        projects = self.repository.project_ids(annotation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="FormAnnotation",
            entity_id=annotation_id,
        )

        link = self.repository.get_tag_link(tag_id, annotation_id)
        if link is not None:
            require_owner_or_project_admin(
                self.scope,
                owner_id=link.CreatorID,
                entity="FormAnnotationTagLink",
                entity_id=None,
                projects=projects,
            )
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
                    actor=self._actor,
                    changes=deleted_data,
                )
        return None


def get_form_annotation_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> FormAnnotationService:
    """Default FormAnnotationService wiring for FastAPI ``Depends()``."""
    return FormAnnotationService(
        FormAnnotationRepository(db, scope=scope),
        ImageInstanceRepository(db, scope=scope),
        TagRepository(db, scope=scope),
        SubTaskRepository(db, scope=scope),
        scope=scope,
        audit=get_audit_service(db),
    )
