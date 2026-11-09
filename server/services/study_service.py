from __future__ import annotations

import logging
from urllib.parse import quote

import httpxyz
from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import Study, StudyTagLink
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository
from eyened_orm.authz.ownership import require_owner, require_owner_or_project_admin
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope

from ..config import DataSource, get_data_sources
from ..db import get_db
from .access_scope import get_access_scope
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import BadRequestError, NotFoundError, UpstreamError

logger = logging.getLogger(__name__)

DATA_SOURCE_TIMEOUT = 10


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

    @staticmethod
    def _sources_for(study: Study) -> list[DataSource]:
        project = study.Patient.Project.ProjectName
        return [s for s in get_data_sources() if project in s.projects]

    def list_data_sources(self, study_id: int) -> list[DataSource]:
        """The configured data sources that apply to a study the actor can see.

        Raises:
            NotFoundError: If the study does not exist or is out of scope.
        """
        return self._sources_for(self._visible_study(study_id))

    def fetch_data_source(self, study_id: int, name: str) -> bytes:
        """Fetch a study's data from the named source; return the upstream body.

        The upstream URL is built from the study's own fields, never from the
        request, so access to the study is access to its data.

        Raises:
            NotFoundError: If the study is missing or out of scope, the source
                does not apply to it, or the upstream has no data (404).
            UpstreamError: If the upstream fails or times out.
        """
        study = self._visible_study(study_id)
        source = next((s for s in self._sources_for(study) if s.name == name), None)
        if source is None:
            raise NotFoundError(f"Data source {name} not found")
        url = source.url.format(
            project=quote(study.Patient.Project.ProjectName, safe=""),
            patient=quote(study.Patient.PatientIdentifier, safe=""),
            date=quote(study.StudyDate.isoformat(), safe=""),
        )
        # The URL is not logged: it holds a patient identifier.
        try:
            with httpxyz.Client(timeout=DATA_SOURCE_TIMEOUT) as client:
                response = client.get(url)
        except httpxyz.HTTPError as exc:
            logger.warning("Data source %s unreachable: %s", name, type(exc).__name__)
            raise UpstreamError(f"Data source {name} unavailable") from None
        if response.status_code == 404:
            raise NotFoundError(f"Data source {name} has no data for this study")
        if not response.is_success:
            logger.warning(
                "Data source %s returned HTTP %s", name, response.status_code
            )
            raise UpstreamError(f"Data source {name} unavailable")
        return response.content


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
