from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import Study, StudyTagLink, Tag


class StudyRepository:
    """Data access for Study rows and their Tag links."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, study_id: int) -> Study | None:
        """Return the study with the given id, or None if absent."""
        return self._session.get(Study, study_id)

    def get_tag(self, tag_id: int) -> Tag | None:
        """Return the tag with the given id, or None if absent.

        Kept here (rather than depending on a future TagRepository) so this
        module migrates independently; ``studies`` only needs to read a Tag to
        validate its ``TagType`` before linking.
        """
        return self._session.get(Tag, tag_id)

    def get_link(self, tag_id: int, study_id: int) -> StudyTagLink | None:
        """Return the StudyTagLink for (tag, study), or None if not linked."""
        return self._session.get(StudyTagLink, {"TagID": tag_id, "StudyID": study_id})

    def add_link(
        self, tag_id: int, study_id: int, creator_id: int, comment: str | None
    ) -> StudyTagLink:
        """Create a StudyTagLink and flush so its row (and PK) is written."""
        link = StudyTagLink(
            TagID=tag_id, StudyID=study_id, CreatorID=creator_id, Comment=comment
        )
        self._session.add(link)
        self._session.flush()
        return link

    def delete_link(self, link: StudyTagLink) -> None:
        """Delete a StudyTagLink and flush so integrity errors surface in-request."""
        self._session.delete(link)
        self._session.flush()
