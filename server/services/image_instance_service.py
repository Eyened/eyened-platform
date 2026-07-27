from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import ImageInstance, ImageInstanceTagLink
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.tag import TagType

from ..db import get_db
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import BadRequestError, NotFoundError


class ImageInstanceService:
    """Business logic for ImageInstance reads and its Tag links."""

    def __init__(
        self,
        repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.tags = tag_repository
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

    def tag_instance(
        self,
        public_id: str,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
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

        link = self.repository.get_tag_link(tag.TagID, instance.ImageInstanceID)
        if link is None:
            link = self.repository.add_link(
                tag_id=tag.TagID,
                image_instance_id=instance.ImageInstanceID,
                creator_id=actor.id,
                comment=comment,
            )
            if self.audit is not None:
                self.audit.record(
                    action="INSERT",
                    entity="ImageInstanceTagLink",
                    actor=actor,
                    changes={
                        "tag_id": tag.TagID,
                        "image_instance_id": instance.ImageInstanceID,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            link.Comment = comment
            # Derive the scalar diff while the mutation is still pending — before
            # the explicit flush() below clears the pending history.
            # ImageInstanceTagLink has a composite PK, so entity_id is null;
            # fold the composite identity into changes (matches the INSERT
            # branch above and untag_instance's DELETE below), or the audit row
            # is unidentifiable. Pre-refactor quirk preserved here: this site's
            # identity uses the raw public_id string, not the int
            # ImageInstanceID (unlike patch_instance_tag's UPDATE below).
            changes = {
                "tag_id": tag.TagID,
                "image_instance_id": public_id,
                **AuditService.diff(link, "Comment"),
            }
            self.repository.flush()
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="ImageInstanceTagLink",
                    actor=actor,
                    changes=changes,
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def patch_instance_tag(
        self,
        public_id: str,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
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

        link = self.repository.get_tag_link(tag_id, instance.ImageInstanceID)
        if link is None:
            raise NotFoundError("Link not found")

        if comment is not None:
            link.Comment = comment
            # Derive the scalar diff while the mutation is still pending — before
            # the explicit flush() below clears the pending history.
            # ImageInstanceTagLink has a composite PK, so entity_id is null;
            # fold the composite identity into changes (matches tag_instance's
            # INSERT/UPDATE and untag_instance's DELETE), or the audit row is
            # unidentifiable. This site's identity uses the int
            # ImageInstanceID (unlike tag_instance's UPDATE above).
            changes = {
                "tag_id": tag_id,
                "image_instance_id": instance.ImageInstanceID,
                **AuditService.diff(link, "Comment"),
            }
            self.repository.flush()
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="ImageInstanceTagLink",
                    actor=actor,
                    changes=changes,
                )

        link.Tag = tag
        return link

    def untag_instance(
        self, public_id: str, tag_id: int, actor: ActingUser
    ) -> None:
        """Remove a Tag from an instance (idempotent; no error if not linked).

        Raises:
            NotFoundError: If the instance does not exist.
        """
        instance = self.repository.get_with_storage_by_public_id(public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")

        link = self.repository.get_tag_link(tag_id, instance.ImageInstanceID)
        if link is not None:
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
                    actor=actor,
                    changes=deleted_data,
                )
        return None


def get_image_instance_service(
    db: Session = Depends(get_db),
) -> ImageInstanceService:
    """Default ImageInstanceService wiring for FastAPI ``Depends()``."""
    return ImageInstanceService(
        ImageInstanceRepository(db), TagRepository(db), audit=get_audit_service(db)
    )
