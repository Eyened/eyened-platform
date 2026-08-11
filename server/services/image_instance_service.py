from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import ImageInstance, ImageInstanceTagLink
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.tag import TagType
from eyened_orm.authz.errors import NotVisibleError
from eyened_orm.authz.ownership import require_owner, require_owner_or_project_admin
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope

from ..db import get_db
from .access_scope import get_access_scope
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import BadRequestError, NotFoundError


class ImageInstanceService:
    """Business logic for ImageInstance reads and its Tag links."""

    def __init__(
        self,
        repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.tags = tag_repository
        self.scope = scope
        self._actor = ActingUser.from_scope(scope)
        self.audit = audit

    def get_instance(
        self,
        instance_id: int,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance:
        """Return an instance by int id, with the requested eager-load graph.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_full_graph_by_id(
            instance_id,
            with_segmentations=with_segmentations,
            with_form_annotations=with_form_annotations,
            with_model_segmentations=with_model_segmentations,
        )
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item

    def get_by_public_id(
        self,
        image_id: str,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance:
        """Return an instance by PublicID, with the requested eager-load graph.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_full_graph_by_public_id(
            image_id,
            with_segmentations=with_segmentations,
            with_form_annotations=with_form_annotations,
            with_model_segmentations=with_model_segmentations,
        )
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item

    def get_for_storage(self, public_id: str) -> ImageInstance:
        """Return the storage-loaded instance for a data/thumbnail request.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_with_storage_by_public_id(public_id)
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item

    def require_grader_on_images(self, image_instance_ids: list[int]) -> None:
        """Require ``grader`` in the project of every supplied image id.

        The RQ worker that executes the job is a trusted non-API path with no
        AccessScope, so it writes wherever it is told: **the enqueue call is
        the boundary**. An unchecked enqueue launders a request the caller
        could not make directly.

        One out-of-scope id fails the whole request. Partial success would let
        a caller probe which ids exist -- the 404 policy applied to a batch.
        """
        by_image = self.repository.project_ids_for_images(image_instance_ids)
        if set(image_instance_ids) - set(by_image):
            # An id that resolves to no image is reported the same way as one
            # the caller cannot see -- otherwise the two answers together are
            # an existence oracle.
            raise NotVisibleError(
                actor_id=self.scope.actor_id,
                entity="ImageInstance",
                entity_id=None,
                projects=frozenset(),
            )
        self.scope.require(
            set(by_image.values()),
            ProjectRole.grader,
            entity="ImageInstance",
            entity_id=None,
        )

    def tag_instance(
        self,
        public_id: str,
        tag_id: int,
        comment: str | None,
    ) -> ImageInstanceTagLink:
        """Attach a Tag to an instance (idempotent; updates comment if re-tagged).

        Raises:
            NotFoundError: If the instance or the tag does not exist.
            BadRequestError: If the tag is not an ImageInstance-type tag.
        """
        instance = self.repository.get_with_storage_by_public_id(public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        tag = self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.ImageInstance:
            raise BadRequestError("Tag type must be ImageInstance")
        # A tag link carries no project of its own, so it is authorized against
        # its *parent* -- the deliberate asymmetry recorded at ``PROJECT_IDS_OF``
        # (``projects_of(session, ImageInstanceTagLink, ...)`` raises by
        # design). The floor therefore names the parent, whose projects it is
        # judged on; the ownership overlay names the link, whose CreatorID it
        # reads, with ``entity_id=None`` because a link's key is composite.
        projects = self.repository.project_ids(instance.ImageInstanceID)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="ImageInstance",
            entity_id=instance.ImageInstanceID,
        )

        link = self.repository.get_tag_link(tag.TagID, instance.ImageInstanceID)
        if link is None:
            link = self.repository.add_link(
                tag_id=tag.TagID,
                image_instance_id=instance.ImageInstanceID,
                creator_id=self.scope.actor_id,
                comment=comment,
            )
            if self.audit is not None:
                self.audit.record(
                    action="INSERT",
                    entity="ImageInstanceTagLink",
                    actor=self._actor,
                    changes={
                        "tag_id": tag.TagID,
                        "image_instance_id": instance.ImageInstanceID,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            # This branch overwrites an existing link's comment, so it is a
            # modify and takes the same overlay ``patch_instance_tag`` does.
            # Without it POST would be a standing bypass of PATCH's check.
            require_owner(
                self.scope,
                owner_id=link.CreatorID,
                entity="ImageInstanceTagLink",
                entity_id=None,
                projects=projects,
            )
            before = AuditService.snapshot(link, "Comment")
            link.Comment = comment
            # ImageInstanceTagLink has a composite PK, so entity_id is null;
            # fold the composite identity into changes (matches the INSERT
            # branch above and untag_instance's DELETE below), or the audit row
            # is unidentifiable. Pre-refactor quirk preserved here: this site's
            # identity uses the raw public_id string, not the int
            # ImageInstanceID (unlike patch_instance_tag's UPDATE below).
            changes = {
                "tag_id": tag.TagID,
                "image_instance_id": public_id,
                **AuditService.diff(before, link),
            }
            self.repository.save_link(link)
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="ImageInstanceTagLink",
                    actor=self._actor,
                    changes=changes,
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def patch_instance_tag(
        self,
        public_id: str,
        tag_id: int,
        comment: str | None,
    ) -> ImageInstanceTagLink:
        """Update the comment on an existing instance tag link.

        Raises:
            NotFoundError: If the instance, tag, or link does not exist.
            BadRequestError: If the tag is not an ImageInstance-type tag.
        """
        instance = self.repository.get_with_storage_by_public_id(public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        tag = self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.ImageInstance:
            raise BadRequestError("Tag type must be ImageInstance")
        projects = self.repository.project_ids(instance.ImageInstanceID)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="ImageInstance",
            entity_id=instance.ImageInstanceID,
        )

        link = self.repository.get_tag_link(tag_id, instance.ImageInstanceID)
        if link is None:
            raise NotFoundError("Link not found")
        require_owner(
            self.scope,
            owner_id=link.CreatorID,
            entity="ImageInstanceTagLink",
            entity_id=None,
            projects=projects,
        )

        if comment is not None:
            before = AuditService.snapshot(link, "Comment")
            link.Comment = comment
            # ImageInstanceTagLink has a composite PK, so entity_id is null;
            # fold the composite identity into changes (matches tag_instance's
            # INSERT/UPDATE and untag_instance's DELETE), or the audit row is
            # unidentifiable. This site's identity uses the int
            # ImageInstanceID (unlike tag_instance's UPDATE above).
            changes = {
                "tag_id": tag_id,
                "image_instance_id": instance.ImageInstanceID,
                **AuditService.diff(before, link),
            }
            self.repository.save_link(link)
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="ImageInstanceTagLink",
                    actor=self._actor,
                    changes=changes,
                )

        link.Tag = tag
        return link

    def untag_instance(self, public_id: str, tag_id: int) -> None:
        """Remove a Tag from an instance (idempotent; no error if not linked).

        Raises:
            NotFoundError: If the instance does not exist.
        """
        instance = self.repository.get_with_storage_by_public_id(public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        projects = self.repository.project_ids(instance.ImageInstanceID)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="ImageInstance",
            entity_id=instance.ImageInstanceID,
        )

        link = self.repository.get_tag_link(tag_id, instance.ImageInstanceID)
        if link is not None:
            require_owner_or_project_admin(
                self.scope,
                owner_id=link.CreatorID,
                entity="ImageInstanceTagLink",
                entity_id=None,
                projects=projects,
            )
            deleted_data = {
                "tag_id": tag_id,
                "image_instance_id": instance.ImageInstanceID,
                "comment": link.Comment,
                "creator_id": link.CreatorID,
            }
            self.repository.delete_link(link)
            if self.audit is not None:
                self.audit.record(
                    action="DELETE",
                    entity="ImageInstanceTagLink",
                    actor=self._actor,
                    changes=deleted_data,
                )
        return None


def get_image_instance_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> ImageInstanceService:
    """Default ImageInstanceService wiring for FastAPI ``Depends()``."""
    return ImageInstanceService(
        ImageInstanceRepository(db, scope=scope),
        TagRepository(db, scope=scope),
        scope=scope,
        audit=get_audit_service(db),
    )
