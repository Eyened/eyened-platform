from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import ImageInstance, ImageInstanceTagLink
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.tag import TagType

from ..db import get_db
from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import BadRequestError, NotFoundError


class ImageInstanceService:
    """Business logic for ImageInstance reads and its Tag links."""

    def __init__(
        self,
        repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.tags = tag_repository
        self.logger = logger

    def get_instance(
        self,
        session: Session,
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
            session,
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
        session: Session,
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
            session,
            image_id,
            with_segmentations=with_segmentations,
            with_form_annotations=with_form_annotations,
            with_model_segmentations=with_model_segmentations,
        )
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item

    def get_for_storage(self, session: Session, public_id: str) -> ImageInstance:
        """Return the storage-loaded instance for a data/thumbnail request.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_with_storage_by_public_id(session, public_id)
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item

    def tag_instance(
        self,
        session: Session,
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
        instance = self.repository.get_with_storage_by_public_id(session, public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        tag = self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.ImageInstance:
            raise BadRequestError("Tag type must be ImageInstance")

        link = self.repository.get_tag_link(
            session, tag.TagID, instance.ImageInstanceID
        )
        if link is None:
            link = ImageInstanceTagLink(
                TagID=tag.TagID,
                ImageInstanceID=instance.ImageInstanceID,
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
                    endpoint=f"POST /api/instances/{public_id}/tags",
                    entity="ImageInstanceTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "image_instance_id": instance.ImageInstanceID,
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
                    endpoint=f"POST /api/instances/{public_id}/tags",
                    entity="ImageInstanceTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "image_instance_id": public_id,
                    },
                    changes={"comment": f"{old_comment} -> {comment}"},
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def patch_instance_tag(
        self,
        session: Session,
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
        instance = self.repository.get_with_storage_by_public_id(session, public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")
        tag = self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.ImageInstance:
            raise BadRequestError("Tag type must be ImageInstance")

        link = self.repository.get_tag_link(
            session, tag_id, instance.ImageInstanceID
        )
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
                    endpoint=f"PATCH /api/instances/{public_id}/tags/{tag_id}",
                    entity="ImageInstanceTagLink",
                    fields={
                        "tag_id": tag_id,
                        "image_instance_id": instance.ImageInstanceID,
                    },
                    changes={"comment": f"{old_comment} -> {comment}"},
                )

        link.Tag = tag
        return link

    def untag_instance(
        self, session: Session, public_id: str, tag_id: int, actor: ActingUser
    ) -> None:
        """Remove a Tag from an instance (idempotent; no error if not linked).

        Raises:
            NotFoundError: If the instance does not exist.
        """
        instance = self.repository.get_with_storage_by_public_id(session, public_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")

        link = self.repository.get_tag_link(
            session, tag_id, instance.ImageInstanceID
        )
        if link is not None:
            deleted_data = {
                "tag_id": tag_id,
                "image_instance_id": instance.ImageInstanceID,
                "comment": link.Comment,
                "creator_id": link.CreatorID,
            }
            session.delete(link)
            session.commit()
            if self.logger is not None:
                self.logger.log_delete(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"DELETE /api/instances/{public_id}/tags/{tag_id}",
                    entity="ImageInstanceTagLink",
                    fields={"tag_id": tag_id, "image_instance_id": public_id},
                    deleted_data=deleted_data,
                )
        return None


def get_image_instance_service(
    db: Session = Depends(get_db),
) -> ImageInstanceService:
    """Default ImageInstanceService wiring for FastAPI ``Depends()``."""
    return ImageInstanceService(
        ImageInstanceRepository(), TagRepository(db), logger=get_db_logger()
    )
