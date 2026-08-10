from __future__ import annotations

from eyened_orm import Tag
from eyened_orm.tag import TagType
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.authz.ownership import require_owner, require_owner_or_project_admin
from eyened_orm.authz.scope import AccessScope
from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from .access_scope import get_access_scope
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import ConflictError, NotFoundError


class TagService:
    """Business logic for tags and per-user tag stars."""

    def __init__(
        self,
        repository: TagRepository,
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.scope = scope
        self._actor = ActingUser.from_scope(scope)
        self.audit = audit

    def list_tags(self) -> list[Tag]:
        """Return all tags (Creator eager-loaded for TagGET)."""
        return self.repository.list_all()

    def create_tag(
        self,
        name: str,
        description: str,
        tag_type: TagType,
    ) -> Tag:
        """Create a tag owned by the acting user."""
        tag = Tag(
            TagName=name,
            TagDescription=description,
            TagType=tag_type,
            CreatorID=self.scope.actor_id,
        )
        self.repository.add(tag)
        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="Tag",
                actor=self._actor,
                entity_id=tag.TagID,
                changes={
                    "name": tag.TagName,
                    "description": tag.TagDescription,
                    "tag_type": tag.TagType,
                },
            )
        return tag

    def update_tag(
        self,
        tag_id: int,
        name: str | None,
        description: str | None,
        tag_type: TagType | None,
    ) -> Tag:
        """Update a tag's name/description/type (each optional).

        Raises:
            NotFoundError: If the tag does not exist.
        """
        tag = self.repository.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        # A Tag is a global label with no project of its own (deliberately
        # absent from PROJECT_IDS_OF -- see orm/eyened_orm/authz/scoping.py).
        # There is no role floor to resolve here; only the ownership overlay
        # binds, and it binds administrators too.
        require_owner(
            self.scope,
            owner_id=tag.CreatorID,
            entity="Tag",
            entity_id=tag_id,
            projects=frozenset(),
        )

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
                actor=self._actor,
                entity_id=tag.TagID,
                changes=changes if changes else None,
            )
        return tag

    def delete_tag(self, tag_id: int) -> None:
        """Delete a tag, unless rows still have it applied.

        Raises:
            NotFoundError: If the tag does not exist.
            ConflictError: If any study/image/annotation/segmentation/form
                annotation still references it (``TAG_IN_USE``). Stars do not
                block a delete -- ``CreatorTag`` still cascades.
        """
        tag = self.repository.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        # A Tag is a global label with no project of its own (deliberately
        # absent from PROJECT_IDS_OF -- see orm/eyened_orm/authz/scoping.py).
        # There is no role floor to resolve here: the owner deletes, or a
        # project_admin does across the (empty) project set -- which Step 3a's
        # fail-closed guard turns into a 404 for everyone else, admins excepted.
        require_owner_or_project_admin(
            self.scope,
            owner_id=tag.CreatorID,
            entity="Tag",
            entity_id=tag_id,
            projects=frozenset(),
        )

        # Read before the delete: a failed flush leaves the Session needing a
        # rollback, so the 409 message must not depend on touching `tag` again.
        tag_name = tag.TagName
        deleted_data = {
            "name": tag_name,
            "description": tag.TagDescription,
            "tag_type": tag.TagType,
        }
        try:
            self.repository.delete(tag)
        except IntegrityError as exc:
            raise ConflictError(
                {
                    "code": "TAG_IN_USE",
                    "message": (
                        f"Cannot delete tag '{tag_name}' because it is still "
                        f"applied to one or more records. Remove those "
                        f"applications first."
                    ),
                }
            ) from exc
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="Tag",
                actor=self._actor,
                entity_id=tag_id,
                changes=deleted_data,
            )
        return None

    def star_tag(self, tag_id: int) -> None:
        """Star a tag for the acting user (idempotent).

        Raises:
            NotFoundError: If the tag does not exist.
        """
        tag = self.repository.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")

        if self.repository.get_star_link(tag_id, self.scope.actor_id) is None:
            self.repository.add_star(tag_id, self.scope.actor_id)
            if self.audit is not None:
                self.audit.record(
                    action="INSERT",
                    entity="CreatorTagLink",
                    actor=self._actor,
                    changes={"tag_id": tag_id, "creator_id": self.scope.actor_id},
                )
        return None

    def unstar_tag(self, tag_id: int) -> None:
        """Remove the acting user's star from a tag (idempotent; no error if absent)."""
        link = self.repository.get_star_link(tag_id, self.scope.actor_id)
        if link is not None:
            self.repository.remove_star(link)
            if self.audit is not None:
                self.audit.record(
                    action="DELETE",
                    entity="CreatorTagLink",
                    actor=self._actor,
                    changes={"tag_id": tag_id, "creator_id": self.scope.actor_id},
                )
        return None


def get_tag_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> TagService:
    """Default TagService wiring for FastAPI ``Depends()``."""
    return TagService(
        TagRepository(db, scope=scope),
        scope=scope,
        audit=get_audit_service(db),
    )
