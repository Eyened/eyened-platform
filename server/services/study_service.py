from __future__ import annotations

import concurrent.futures
import logging

from fastapi import Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from eyened_orm import Study, StudyTagLink
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository
from eyened_orm.authz.ownership import require_owner, require_owner_or_project_admin
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope

from ..db import get_db
from ..study_extension import (
    StudyExtension,
    TablesContribution,
    extension_context,
    get_extensions,
)
from .access_scope import get_access_scope
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import BadRequestError, NotFoundError, UpstreamError

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 10


class StudyService:
    """Business logic for tagging studies and reading their external data sources."""

    def __init__(
        self,
        repository: StudyRepository,
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.scope = scope
        self._actor = ActingUser.from_scope(scope)
        self.audit = audit

    def tag_study(
        self,
        study_id: int,
        tag_id: int,
        comment: str | None,
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
        # A tag link carries no project of its own, so it is authorized against
        # its *parent* -- the deliberate asymmetry recorded at ``PROJECT_IDS_OF``
        # (``projects_of(session, StudyTagLink, ...)`` raises by design). The
        # floor therefore names the parent, whose projects it is judged on; the
        # ownership overlay names the link, whose CreatorID it reads, with
        # ``entity_id=None`` because a link's primary key is composite.
        projects = self.repository.project_ids(study_id)
        self.scope.require(
            projects, ProjectRole.grader, entity="Study", entity_id=study_id
        )

        link = self.repository.get_link(tag_id, study_id)
        if link is None:
            link = self.repository.add_link(
                tag_id=tag.TagID,
                study_id=study_id,
                creator_id=self.scope.actor_id,
                comment=comment,
            )
            link.Tag = tag
            if self.audit is not None:
                self.audit.record(
                    action="INSERT",
                    entity="StudyTagLink",
                    actor=self._actor,
                    changes={
                        "tag_id": tag.TagID,
                        "study_id": study_id,
                        "comment": comment,
                    },
                )
        elif comment is not None:
            # This branch overwrites an existing link's comment, so it is a
            # modify and takes the same overlay ``patch_study_tag`` does.
            # Without it POST would be a standing bypass of PATCH's check.
            require_owner(
                self.scope,
                owner_id=link.CreatorID,
                entity="StudyTagLink",
                entity_id=None,
                projects=projects,
            )
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
                    actor=self._actor,
                    changes=changes,
                )
        return link

    def untag_study(
        self,
        study_id: int,
        tag_id: int,
    ) -> None:
        """Remove a Study tag from a study (idempotent).

        Raises:
            NotFoundError: If the study does not exist.
        """
        study = self.repository.get_by_id(study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        projects = self.repository.project_ids(study_id)
        self.scope.require(
            projects, ProjectRole.grader, entity="Study", entity_id=study_id
        )
        link = self.repository.get_link(tag_id, study_id)
        if link is None:
            return None
        require_owner_or_project_admin(
            self.scope,
            owner_id=link.CreatorID,
            entity="StudyTagLink",
            entity_id=None,
            projects=projects,
        )

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
                actor=self._actor,
                changes=deleted_data,
            )
        return None

    def patch_study_tag(
        self,
        study_id: int,
        tag_id: int,
        comment: str | None,
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
        projects = self.repository.project_ids(study_id)
        self.scope.require(
            projects, ProjectRole.grader, entity="Study", entity_id=study_id
        )
        link = self.repository.get_link(tag_id, study_id)
        if link is None:
            raise NotFoundError(f"Tag {tag_id} is not linked to study {study_id}")
        require_owner(
            self.scope,
            owner_id=link.CreatorID,
            entity="StudyTagLink",
            entity_id=None,
            projects=projects,
        )

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
                    actor=self._actor,
                    changes=changes,
                )
        link.Tag = tag
        return link

    def _visible_study(self, study_id: int) -> Study:
        study = self.repository.get_by_id(study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        return study

    def _context(self, study: Study):
        return extension_context(
            study,
            actor_id=self._actor.id,
            actor_username=self._actor.username,
            session=self.repository.session,
        )

    def _extensions_for(self, study: Study) -> list[StudyExtension]:
        ctx = self._context(study)
        matched: list[StudyExtension] = []
        for extension in get_extensions():
            try:
                applies = extension.applies(ctx)
            except Exception as exc:
                logger.warning(
                    "Data source %s applies failed: %s",
                    extension.name,
                    type(exc).__name__,
                )
                continue
            if applies:
                matched.append(extension)
        return matched

    def list_data_sources(self, study_id: int) -> list[StudyExtension]:
        """The extensions that apply to a study the actor can see.

        Raises:
            NotFoundError: If the study does not exist or is out of scope.
        """
        return self._extensions_for(self._visible_study(study_id))

    def fetch_data_source(self, study_id: int, name: str) -> TablesContribution:
        """Run the named extension's fetch for a visible study.

        Raises:
            NotFoundError: If the study is missing or out of scope, the
                extension does not apply, or fetch returns None.
            UpstreamError: If fetch raises, times out, or returns a bad envelope.
        """
        study = self._visible_study(study_id)
        ctx = self._context(study)
        extension = next(
            (e for e in get_extensions() if e.name == name and e.applies(ctx)),
            None,
        )
        if extension is None:
            raise NotFoundError(f"Data source {name} not found")
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(extension.fetch, ctx)
            try:
                result = future.result(timeout=FETCH_TIMEOUT)
            except concurrent.futures.TimeoutError:
                logger.warning("Data source %s timed out", name)
                raise UpstreamError(f"Data source {name} unavailable") from None
            except Exception as exc:
                logger.warning("Data source %s failed: %s", name, type(exc).__name__)
                raise UpstreamError(f"Data source {name} unavailable") from None
        finally:
            pool.shutdown(wait=False)
        if result is None:
            raise NotFoundError(f"Data source {name} has no data for this study")
        try:
            if isinstance(result, TablesContribution):
                return result
            return TablesContribution.model_validate(result)
        except ValidationError:
            logger.warning("Data source %s returned an invalid envelope", name)
            raise UpstreamError(f"Data source {name} unavailable") from None


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
