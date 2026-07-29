from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, noload, selectinload

from eyened_orm import Creator, CreatorTagLink, Tag


class TagRepository:
    """Data access for Tag rows and their per-user 'star' links."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, tag: Tag) -> None:
        """Stage a new tag and flush so its PK is assigned."""
        self._session.add(tag)
        self._session.flush()

    def delete(self, tag: Tag) -> None:
        """Delete a tag and flush within the request transaction."""
        self._session.delete(tag)
        self._session.flush()

    def get_by_id(self, tag_id: int) -> Tag | None:
        """Return the tag with the given id, or None if absent."""
        return self._session.get(Tag, tag_id)

    def save(self, tag: Tag) -> None:
        """Persist in-place mutations to ``tag`` within the request transaction.

        ``tag`` names what is being saved; the flush covers the whole unit of
        work, deliberately not just this row.
        """
        self._session.flush()

    def list_all(self) -> list[Tag]:
        """Return all tags, loading only what TagGET needs.

        Tag has six ``lazy="selectin"`` link collections; TagGET only needs the
        Tag columns plus its Creator (id, name). We ``noload`` those collections
        and ``selectinload`` just the Creator so listing tags does not fan out
        into six extra per-tag queries. (Mirrors the query previously inline in
        the ``GET /tags`` handler.) Ordering is unspecified (DB order), as today.
        """
        stmt = select(Tag).options(
            load_only(
                Tag.TagID,
                Tag.TagName,
                Tag.TagType,
                Tag.TagDescription,
                Tag.CreatorID,
                Tag.DateInserted,
            ),
            noload(Tag.CreatorTagLinks),
            noload(Tag.StudyTagLinks),
            noload(Tag.ImageInstanceTagLinks),
            noload(Tag.AnnotationTagLinks),
            noload(Tag.SegmentationTagLinks),
            noload(Tag.FormAnnotationTagLinks),
            selectinload(Tag.Creator).load_only(
                Creator.CreatorID, Creator.CreatorName
            ),
        )
        return list(self._session.scalars(stmt).all())

    def get_star_link(
        self, tag_id: int, creator_id: int
    ) -> CreatorTagLink | None:
        """Return the star link for (tag, creator), or None if not starred."""
        return self._session.get(
            CreatorTagLink, {"TagID": tag_id, "CreatorID": creator_id}
        )

    def add_star(self, tag_id: int, creator_id: int) -> CreatorTagLink:
        """Create a star link (tag, creator) and flush so its row is written."""
        link = CreatorTagLink(TagID=tag_id, CreatorID=creator_id)
        self._session.add(link)
        self._session.flush()
        return link

    def remove_star(self, link: CreatorTagLink) -> None:
        """Delete a star link and flush within the request transaction."""
        self._session.delete(link)
        self._session.flush()
