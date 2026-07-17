from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from eyened_orm import ModelSegmentation, Segmentation
from eyened_orm.tag import SegmentationTagLink


class SegmentationRepository:
    """Data access for Segmentation reads and its Tag links."""

    def get_by_id(
        self, session: Session, segmentation_id: int
    ) -> Segmentation | None:
        """Return the segmentation by id, or None if absent."""
        return session.get(Segmentation, segmentation_id)

    def get_with_tag_links(
        self, session: Session, segmentation_id: int
    ) -> Segmentation | None:
        """Return the segmentation with its tag links loaded, or None.

        Mirrors the eager-load graph the ``GET /segmentations/{id}`` handler
        built inline.
        """
        return session.get(
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
        self, session: Session, tag_id: int, segmentation_id: int
    ) -> SegmentationTagLink | None:
        """Return the link for (tag_id, segmentation_id), or None if absent."""
        return session.get(
            SegmentationTagLink,
            {"TagID": tag_id, "SegmentationID": segmentation_id},
        )


class ModelSegmentationRepository:
    """Data access for ModelSegmentation reads (data endpoints only)."""

    def get_by_id(
        self, session: Session, model_segmentation_id: int
    ) -> ModelSegmentation | None:
        """Return the model segmentation by id, or None if absent."""
        return session.get(ModelSegmentation, model_segmentation_id)
