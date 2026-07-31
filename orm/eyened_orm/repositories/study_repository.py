from __future__ import annotations

from sqlalchemy.orm import Session, noload

from eyened_orm import Study, StudyTagLink, Tag
from eyened_orm.tag import TAG_LINK_COLLECTIONS


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
        module migrates independently. ``studies`` reads ``TagType`` to validate
        the link (``study_service.py:46``) and then assigns the instance into
        ``StudyTagLink.Tag`` (``:57``) -- which is why this returns the mapped
        object rather than the single column. A ``select(Tag.TagType)`` would be
        cheaper still and would leave nothing in the identity map at all, but it
        would break that assignment.

        The link collections are ``noload``-ed for the same reason
        ``TagRepository.get_by_id`` does it: ``Tag`` maps them
        ``lazy="selectin"``, so a plain ``session.get()`` loads all six -- on
        the dev database that is up to 76k rows to read one column. It also
        keeps a loaded collection out of the Session, which is what would
        otherwise let the ORM pre-empt the delete-time foreign keys (§3.2.1).
        """
        return self._session.get(
            Tag,
            tag_id,
            options=[noload(attribute) for attribute in TAG_LINK_COLLECTIONS],
        )

    def get_link(self, tag_id: int, study_id: int) -> StudyTagLink | None:
        """Return the StudyTagLink for (tag, study), or None if not linked."""
        return self._session.get(StudyTagLink, {"TagID": tag_id, "StudyID": study_id})

    def save_link(self, link: StudyTagLink) -> None:
        """Persist in-place mutations to ``link`` (e.g. ``Comment``) within the
        request transaction.

        ``link`` names what is being saved; the flush covers the whole unit of
        work, deliberately not just this row.
        """
        self._session.flush()

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
        """Delete a StudyTagLink and flush within the request transaction."""
        self._session.delete(link)
        self._session.flush()
