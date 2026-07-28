from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from eyened_orm import ModelSegmentation, Segmentation
from eyened_orm.tag import SegmentationTagLink


class SegmentationRepository:
    """Data access for Segmentation reads, mutations, and its Tag links."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, segmentation_id: int) -> Segmentation | None:
        """Return the segmentation by id, or None if absent."""
        return self._session.get(Segmentation, segmentation_id)

    def get_with_tag_links(self, segmentation_id: int) -> Segmentation | None:
        """Return the segmentation with its tag links loaded, or None.

        Mirrors the eager-load graph the ``GET /segmentations/{id}`` handler
        built inline.
        """
        return self._session.get(
            Segmentation,
            segmentation_id,
            options=(
                selectinload(Segmentation.SegmentationTagLinks).selectinload(
                    SegmentationTagLink.Tag
                ),
                selectinload(Segmentation.SegmentationTagLinks).selectinload(
                    SegmentationTagLink.Creator
                ),
            ),
        )

    def get_tag_link(
        self, tag_id: int, segmentation_id: int
    ) -> SegmentationTagLink | None:
        """Return the link for (tag_id, segmentation_id), or None if absent."""
        return self._session.get(
            SegmentationTagLink,
            {"TagID": tag_id, "SegmentationID": segmentation_id},
        )

    def add(self, segmentation: Segmentation) -> None:
        """Stage a new Segmentation and flush so its PK/server defaults populate."""
        self._session.add(segmentation)
        self._session.flush()

    def save(self, segmentation: Segmentation) -> None:
        """Persist in-place mutations to ``segmentation`` (e.g. ``Inactive``,
        ``Threshold``, ``FeatureID``, ``ReferenceSegmentationID``) within the
        request transaction.

        ``segmentation`` names what is being saved; the flush covers the whole
        unit of work, deliberately not just this row.
        """
        self._session.flush()

    def add_link(
        self, *, tag_id: int, segmentation_id: int, creator_id: int
    ) -> SegmentationTagLink:
        """Create a SegmentationTagLink and flush so its row (and PK) is written."""
        link = SegmentationTagLink(
            TagID=tag_id,
            SegmentationID=segmentation_id,
            CreatorID=creator_id,
        )
        self._session.add(link)
        self._session.flush()
        return link

    def delete_link(self, link: SegmentationTagLink) -> None:
        """Delete a SegmentationTagLink and flush so integrity errors surface in-request."""
        self._session.delete(link)
        self._session.flush()


class ModelSegmentationRepository:
    """Data access for ModelSegmentation reads and mutations (data endpoints only)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, model_segmentation_id: int) -> ModelSegmentation | None:
        """Return the model segmentation by id, or None if absent."""
        return self._session.get(ModelSegmentation, model_segmentation_id)

    def save(self, model_segmentation: ModelSegmentation) -> None:
        """Persist in-place mutations to ``model_segmentation`` (e.g.
        ``ZarrArrayIndex``) within the request transaction.

        ``model_segmentation`` names what is being saved; the flush covers the
        whole unit of work, deliberately not just this row.
        """
        self._session.flush()
