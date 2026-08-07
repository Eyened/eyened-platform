from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import StudyTagLink
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository
from eyened_orm.authz.scope import AccessScope

from ..db import get_db
from .access_scope import get_access_scope
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import BadRequestError, NotFoundError


class StudyService:
    """Business logic for tagging studies."""

    def __init__(
        self,
        repository: StudyRepository,
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.scope = scope
        self.audit = audit

    def tag_study(
        self,
        study_id: int,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> StudyTagLink:
        """Attach a Study tag to a study (idempotent; updates comment if linked).

        Raises:
            NotFoundError: If the study or tag does not exist.
            BadRequestError: If the tag's type is not ``TagType.Study``.
        """
        study = self.repository.get_by_id(study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        tag = self.repository.get_tag(tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        if tag.TagType != TagType.Study:
            raise BadRequestError("Tag type must be Study")

        link = self.repository.get_link(tag_id, study_id)
        if link is None:
            link = self.repository.add_link(
                tag_id=tag.TagID,
                study_id=study_id,
                creator_id=actor.id,
                comment=comment,
            )
            link.Tag = tag
            if self.audit is not None:
                self.audit.record(
                    action="INSERT",
                    entity="StudyTagLink",
                    actor=actor,
                    changes={
                        "tag_id": tag.TagID,
                        "study_id": study_id,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            before = AuditService.snapshot(link, "Comment")
            link.Comment = comment
            # StudyTagLink has a composite PK, so entity_id is null; fold the
            # composite identity into changes (matches the INSERT branch above
            # and the DELETE below), or the audit row is unidentifiable.
            changes = {
                "tag_id": tag.TagID,
                "study_id": study_id,
                **AuditService.diff(before, link),
            }
            self.repository.save_link(link)
            link.Tag = tag
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="StudyTagLink",
                    actor=actor,
                    changes=changes,
                )
        return link

    def untag_study(
        self,
        study_id: int,
        tag_id: int,
        actor: ActingUser,
    ) -> None:
        """Remove a Study tag from a study (idempotent).

        Raises:
            NotFoundError: If the study does not exist.
        """
        study = self.repository.get_by_id(study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        link = self.repository.get_link(tag_id, study_id)
        if link is None:
            return None

        deleted_data = {
            "tag_id": tag_id,
            "study_id": study_id,
            "comment": link.Comment,
            "creator_id": link.CreatorID,
        }
        self.repository.delete_link(link)
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="StudyTagLink",
                actor=actor,
                changes=deleted_data,
            )
        return None

    def patch_study_tag(
        self,
        study_id: int,
        tag_id: int,
        comment: str | None,
        actor: ActingUser,
    ) -> StudyTagLink:
        """Update the comment on an existing Study tag link.

        Raises:
            NotFoundError: If the study, tag, or link does not exist.
            BadRequestError: If the tag's type is not ``TagType.Study``.
        """
        study = self.repository.get_by_id(study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        tag = self.repository.get_tag(tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        if tag.TagType != TagType.Study:
            raise BadRequestError("Tag type must be Study")
        link = self.repository.get_link(tag_id, study_id)
        if link is None:
            raise NotFoundError(f"Tag {tag_id} is not linked to study {study_id}")

        if comment is not None:
            before = AuditService.snapshot(link, "Comment")
            link.Comment = comment
            # StudyTagLink has a composite PK, so entity_id is null; fold the
            # composite identity into changes (matches tag_study's INSERT/UPDATE
            # and untag_study's DELETE), or the audit row is unidentifiable.
            changes = {
                "tag_id": tag_id,
                "study_id": study_id,
                **AuditService.diff(before, link),
            }
            self.repository.save_link(link)
            if self.audit is not None:
                self.audit.record(
                    action="UPDATE",
                    entity="StudyTagLink",
                    actor=actor,
                    changes=changes,
                )
        link.Tag = tag
        return link


def get_study_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> StudyService:
    """Default StudyService wiring for FastAPI ``Depends()``."""
    return StudyService(
        StudyRepository(db, scope=scope),
        scope=scope,
        audit=get_audit_service(db),
    )
