from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import StudyTagLink
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import BadRequestError, NotFoundError


class StudyService:
    """Business logic for tagging studies."""

    def __init__(
        self,
        repository: StudyRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.logger = logger

    def tag_study(
        self,
        session: Session,
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
        study = self.repository.get_by_id(session, study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        tag = self.repository.get_tag(session, tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        if tag.TagType != TagType.Study:
            raise BadRequestError("Tag type must be Study")

        link = self.repository.get_link(session, tag_id, study_id)
        if link is None:
            link = StudyTagLink(
                TagID=tag.TagID,
                StudyID=study_id,
                CreatorID=actor.id,
                Comment=comment,
            )
            session.add(link)
            session.commit()
            session.refresh(link)
            link.Tag = tag
            if self.logger is not None:
                self.logger.log_insert(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/studies/{study_id}/tags",
                    entity="StudyTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "study_id": study_id,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            old_comment = link.Comment
            link.Comment = comment
            session.commit()
            session.refresh(link)
            link.Tag = tag
            if self.logger is not None:
                self.logger.log_update(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/studies/{study_id}/tags",
                    entity="StudyTagLink",
                    fields={"tag_id": tag.TagID, "study_id": study_id},
                    changes={"comment": f"{old_comment} -> {comment}"},
                )
        return link

    def untag_study(
        self,
        session: Session,
        study_id: int,
        tag_id: int,
        actor: ActingUser,
    ) -> None:
        """Remove a Study tag from a study (idempotent).

        Raises:
            NotFoundError: If the study does not exist.
        """
        study = self.repository.get_by_id(session, study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        link = self.repository.get_link(session, tag_id, study_id)
        if link is None:
            return None

        deleted_data = {
            "tag_id": tag_id,
            "study_id": study_id,
            "comment": link.Comment,
            "creator_id": link.CreatorID,
        }
        session.delete(link)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/studies/{study_id}/tags/{tag_id}",
                entity="StudyTagLink",
                fields={"tag_id": tag_id, "study_id": study_id},
                deleted_data=deleted_data,
            )
        return None

    def patch_study_tag(
        self,
        session: Session,
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
        study = self.repository.get_by_id(session, study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        tag = self.repository.get_tag(session, tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        if tag.TagType != TagType.Study:
            raise BadRequestError("Tag type must be Study")
        link = self.repository.get_link(session, tag_id, study_id)
        if link is None:
            raise NotFoundError(f"Tag {tag_id} is not linked to study {study_id}")

        if comment is not None:
            old_comment = link.Comment
            link.Comment = comment
            session.commit()
            session.refresh(link)
            if self.logger is not None:
                self.logger.log_update(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"PATCH /api/studies/{study_id}/tags/{tag_id}",
                    entity="StudyTagLink",
                    fields={"tag_id": tag_id, "study_id": study_id},
                    changes={"comment": f"{old_comment} -> {comment}"},
                )
        link.Tag = tag
        return link


def get_study_service() -> StudyService:
    """Default StudyService wiring for FastAPI ``Depends()``."""
    return StudyService(StudyRepository(), logger=get_db_logger())
