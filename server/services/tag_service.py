from __future__ import annotations

from eyened_orm import Tag
from eyened_orm.tag import TagType
from eyened_orm.repositories.tag_repository import TagRepository
from fastapi import Depends
from sqlalchemy.orm import Session

from ..db import get_db
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import NotFoundError


class TagService:
    """Business logic for tags and per-user tag stars."""

    def __init__(
        self,
        repository: TagRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.audit = audit

    def list_tags(self) -> list[Tag]:
        """Return all tags (Creator eager-loaded for TagGET)."""
        return self.repository.list_all()

    def create_tag(
        self,
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
        self.repository.add(tag)
        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="Tag",
                actor=actor,
                entity_id=tag.TagID,
                changes={
                    "name": tag.TagName,
                    "description": tag.TagDescription,
                    "tag_type": str(tag.TagType),
                },
            )
        return tag

    def update_tag(
        self,
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
        tag = self.repository.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")

        before = AuditService.snapshot(tag, "TagName", "TagDescription", "TagType")
        if name is not None:
            tag.TagName = name
        if description is not None:
            tag.TagDescription = description
        if tag_type is not None:
            tag.TagType = tag_type

        changes = AuditService.diff(before, tag)
        self.repository.save(tag)

        if self.audit is not None:
            self.audit.record(
                action="UPDATE",
                entity="Tag",
                actor=actor,
                entity_id=tag.TagID,
                changes=changes if changes else None,
            )
        return tag

    def delete_tag(self, tag_id: int, actor: ActingUser) -> None:
        """Delete a tag.

        Raises:
            NotFoundError: If the tag does not exist.
        """
        tag = self.repository.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")

        deleted_data = {
            "name": tag.TagName,
            "description": tag.TagDescription,
            "tag_type": tag.TagType,
        }
        self.repository.delete(tag)
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="Tag",
                actor=actor,
                entity_id=tag_id,
                changes=deleted_data,
            )
        return None

    def star_tag(self, tag_id: int, actor: ActingUser) -> None:
        """Star a tag for the acting user (idempotent).

        Raises:
            NotFoundError: If the tag does not exist.
        """
        tag = self.repository.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")

        if self.repository.get_star_link(tag_id, actor.id) is None:
            self.repository.add_star(tag_id, actor.id)
            if self.audit is not None:
                self.audit.record(
                    action="INSERT",
                    entity="CreatorTagLink",
                    actor=actor,
                    changes={"tag_id": tag_id, "creator_id": actor.id},
                )
        return None

    def unstar_tag(self, tag_id: int, actor: ActingUser) -> None:
        """Remove the acting user's star from a tag (idempotent; no error if absent)."""
        link = self.repository.get_star_link(tag_id, actor.id)
        if link is not None:
            self.repository.remove_star(link)
            if self.audit is not None:
                self.audit.record(
                    action="DELETE",
                    entity="CreatorTagLink",
                    actor=actor,
                    changes={"tag_id": tag_id, "creator_id": actor.id},
                )
        return None


def get_tag_service(db: Session = Depends(get_db)) -> TagService:
    """Default TagService wiring for FastAPI ``Depends()``."""
    return TagService(TagRepository(db), audit=get_audit_service(db))
