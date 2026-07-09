from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import CreatorTagLink, Tag
from eyened_orm.tag import TagType
from eyened_orm.repositories.tag_repository import TagRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import NotFoundError


class TagService:
    """Business logic for tags and per-user tag stars."""

    def __init__(
        self,
        repository: TagRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.logger = logger

    def list_tags(self, session: Session) -> list[Tag]:
        """Return all tags (Creator eager-loaded for TagGET)."""
        return self.repository.list_all(session)

    def create_tag(
        self,
        session: Session,
        name: str,
        description: str,
        tag_type: TagType,
        actor: ActingUser,
    ) -> Tag:
        """Create a tag owned by the acting user."""
        tag = Tag(
            TagName=name,
            TagDescription=description,
            TagType=tag_type,
            CreatorID=actor.id,
        )
        session.add(tag)
        session.commit()
        session.refresh(tag)
        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint="POST /api/tags",
                entity="Tag",
                entity_id=tag.TagID,
                fields={
                    "name": tag.TagName,
                    "description": tag.TagDescription,
                    "tag_type": str(tag.TagType),
                },
            )
        return tag

    def update_tag(
        self,
        session: Session,
        tag_id: int,
        name: str | None,
        description: str | None,
        tag_type: TagType | None,
        actor: ActingUser,
    ) -> Tag:
        """Update a tag's name/description/type (each optional).

        Raises:
            NotFoundError: If the tag does not exist.
        """
        tag = self.repository.get_by_id(session, tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")

        changes: dict[str, str] = {}
        if name is not None:
            changes["name"] = f"{tag.TagName} -> {name}"
            tag.TagName = name
        if description is not None:
            changes["description"] = f"{tag.TagDescription} -> {description}"
            tag.TagDescription = description
        if tag_type is not None:
            changes["tag_type"] = f"{tag.TagType} -> {tag_type}"
            tag.TagType = tag_type

        session.commit()
        session.refresh(tag)
        if self.logger is not None:
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/tags/{tag_id}",
                entity="Tag",
                entity_id=tag.TagID,
                changes=changes if changes else None,
            )
        return tag

    def delete_tag(
        self, session: Session, tag_id: int, actor: ActingUser
    ) -> None:
        """Delete a tag.

        Raises:
            NotFoundError: If the tag does not exist.
        """
        tag = self.repository.get_by_id(session, tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")

        deleted_data = {
            "name": tag.TagName,
            "description": tag.TagDescription,
            "tag_type": str(tag.TagType),
        }
        session.delete(tag)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/tags/{tag_id}",
                entity="Tag",
                entity_id=tag_id,
                deleted_data=deleted_data,
            )
        return None

    def star_tag(
        self, session: Session, tag_id: int, actor: ActingUser
    ) -> None:
        """Star a tag for the acting user (idempotent).

        Raises:
            NotFoundError: If the tag does not exist.
        """
        tag = self.repository.get_by_id(session, tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")

        if self.repository.get_star_link(session, tag_id, actor.id) is None:
            session.add(CreatorTagLink(TagID=tag_id, CreatorID=actor.id))
            session.commit()
            if self.logger is not None:
                self.logger.log_insert(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/tags/{tag_id}/star",
                    entity="CreatorTagLink",
                    fields={"tag_id": tag_id, "creator_id": actor.id},
                )
        return None

    def unstar_tag(
        self, session: Session, tag_id: int, actor: ActingUser
    ) -> None:
        """Remove the acting user's star from a tag (idempotent; no error if absent)."""
        link = self.repository.get_star_link(session, tag_id, actor.id)
        if link is not None:
            session.delete(link)
            session.commit()
            if self.logger is not None:
                self.logger.log_delete(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"DELETE /api/tags/{tag_id}/star",
                    entity="CreatorTagLink",
                    fields={"tag_id": tag_id, "creator_id": actor.id},
                )
        return None


def get_tag_service() -> TagService:
    """Default TagService wiring for FastAPI ``Depends()``."""
    return TagService(TagRepository(), logger=get_db_logger())
