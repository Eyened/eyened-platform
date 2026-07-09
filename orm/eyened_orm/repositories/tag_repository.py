from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, noload, selectinload

from eyened_orm import Creator, CreatorTagLink, Tag


class TagRepository:
    """Data access for Tag rows and their per-user 'star' links."""

    def get_by_id(self, session: Session, tag_id: int) -> Tag | None:
        """Return the tag with the given id, or None if absent."""
        return session.get(Tag, tag_id)

    def list_all(self, session: Session) -> list[Tag]:
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
        return list(session.scalars(stmt).all())

    def get_star_link(
        self, session: Session, tag_id: int, creator_id: int
    ) -> CreatorTagLink | None:
        """Return the star link for (tag, creator), or None if not starred."""
        return session.get(
            CreatorTagLink, {"TagID": tag_id, "CreatorID": creator_id}
        )
