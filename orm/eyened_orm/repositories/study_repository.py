from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import Study, StudyTagLink, Tag


class StudyRepository:
    """Data access for Study rows and their Tag links."""

    def get_by_id(self, session: Session, study_id: int) -> Study | None:
        """Return the study with the given id, or None if absent."""
        return session.get(Study, study_id)

    def get_tag(self, session: Session, tag_id: int) -> Tag | None:
        """Return the tag with the given id, or None if absent.

        Kept here (rather than depending on a future TagRepository) so this
        module migrates independently; ``studies`` only needs to read a Tag to
        validate its ``TagType`` before linking.
        """
        return session.get(Tag, tag_id)

    def get_link(
        self, session: Session, tag_id: int, study_id: int
    ) -> StudyTagLink | None:
        """Return the StudyTagLink for (tag, study), or None if not linked."""
        return session.get(StudyTagLink, {"TagID": tag_id, "StudyID": study_id})
