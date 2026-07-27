from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, selectinload

from eyened_orm import (
    DeviceInstance,
    FormAnnotation,
    ImageInstance,
    ImageInstanceTagLink,
    ImageStorage,
    ModelSegmentation,
    Patient,
    Segmentation,
    Series,
    Study,
)
from eyened_orm.tag import FormAnnotationTagLink, SegmentationTagLink

_STORAGE_LOADER = selectinload(ImageInstance.ImageStorages).selectinload(
    ImageStorage.StorageBackend
)


def _full_graph_options(
    with_segmentations: bool,
    with_form_annotations: bool,
    with_model_segmentations: bool,
) -> list:
    """Build the conditional selectinload chain the two GET readers share."""
    opts = [
        selectinload(ImageInstance.Series)
        .selectinload(Series.Study)
        .selectinload(Study.Patient)
        .selectinload(Patient.Project),
        selectinload(ImageInstance.DeviceInstance).selectinload(
            DeviceInstance.DeviceModel
        ),
        selectinload(ImageInstance.Scan),
        _STORAGE_LOADER,
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
            ImageInstanceTagLink.Tag
        ),
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
            ImageInstanceTagLink.Creator
        ),
    ]
    if with_segmentations:
        opts += [
            selectinload(ImageInstance.Segmentations).selectinload(
                Segmentation.Feature
            ),
            selectinload(ImageInstance.Segmentations).selectinload(
                Segmentation.Creator
            ),
            selectinload(ImageInstance.Segmentations)
            .selectinload(Segmentation.SegmentationTagLinks)
            .selectinload(SegmentationTagLink.Tag),
            selectinload(ImageInstance.Segmentations)
            .selectinload(Segmentation.SegmentationTagLinks)
            .selectinload(SegmentationTagLink.Creator),
        ]
    if with_form_annotations:
        opts += [
            selectinload(ImageInstance.FormAnnotations)
            .selectinload(FormAnnotation.FormAnnotationTagLinks)
            .selectinload(FormAnnotationTagLink.Tag),
            selectinload(ImageInstance.FormAnnotations)
            .selectinload(FormAnnotation.FormAnnotationTagLinks)
            .selectinload(FormAnnotationTagLink.Creator),
        ]
    if with_model_segmentations:
        opts += [
            selectinload(ImageInstance.ModelSegmentations).selectinload(
                ModelSegmentation.Model
            ),
        ]
    return opts


class ImageInstanceRepository:
    """Data access for ImageInstance reads and its Tag links."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_full_graph_by_id(
        self,
        instance_id: int,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance | None:
        """Return the instance by int id with the conditional graph, or None."""
        opts = _full_graph_options(
            with_segmentations, with_form_annotations, with_model_segmentations
        )
        return self._session.get(ImageInstance, instance_id, options=tuple(opts))

    def get_full_graph_by_public_id(
        self,
        image_id: str,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance | None:
        """Return the instance by PublicID (numeric-PK fallback), or None."""
        opts = _full_graph_options(
            with_segmentations, with_form_annotations, with_model_segmentations
        )
        item = (
            self._session.scalars(
                select(ImageInstance)
                .options(*opts)
                .where(ImageInstance.PublicID == image_id)
            )
            .first()
        )
        if item is None and image_id.isdigit():
            item = self._session.get(
                ImageInstance, int(image_id), options=tuple(opts)
            )
        return item

    def get_with_storage_by_public_id(
        self, public_id: str
    ) -> ImageInstance | None:
        """Return the instance by PublicID with storage loaded (PK fallback), or None.

        Mirrors the legacy ``_get_image_instance_by_public_id`` resolver: try the
        PublicID; on no match fall back to ``session.get`` with the raw id.
        """
        try:
            return self._session.scalars(
                select(ImageInstance)
                .options(_STORAGE_LOADER)
                .where(ImageInstance.PublicID == public_id)
            ).one()
        except NoResultFound:
            return self._session.get(ImageInstance, public_id)

    def get_tag_link(
        self, tag_id: int, image_instance_id: int
    ) -> ImageInstanceTagLink | None:
        """Return the link for (tag_id, image_instance_id), or None if absent."""
        return self._session.get(
            ImageInstanceTagLink,
            {"TagID": tag_id, "ImageInstanceID": image_instance_id},
        )

    def flush(self) -> None:
        """Flush pending in-place ImageInstanceTagLink mutations (e.g.
        ``Comment``) so integrity errors surface in-request within the
        request transaction."""
        self._session.flush()

    def get_by_public_id(self, public_id: str) -> ImageInstance | None:
        """Return the instance with this PublicID (no eager loads), or None.

        Plain PublicID resolver used to map an external image id to its row —
        the faithful equivalent of the legacy ``_resolve_image_instance_id``
        helper (no PK/digit fallback, unlike ``get_full_graph_by_public_id``).
        """
        return self._session.scalars(
            select(ImageInstance).where(ImageInstance.PublicID == public_id)
        ).first()

    def add_link(
        self,
        *,
        tag_id: int,
        image_instance_id: int,
        creator_id: int,
        comment: str | None,
    ) -> ImageInstanceTagLink:
        """Create an ImageInstanceTagLink and flush so its row (and PK) is written."""
        link = ImageInstanceTagLink(
            TagID=tag_id,
            ImageInstanceID=image_instance_id,
            CreatorID=creator_id,
            Comment=comment,
        )
        self._session.add(link)
        self._session.flush()
        return link

    def delete_link(self, link: ImageInstanceTagLink) -> None:
        """Delete an ImageInstanceTagLink and flush so integrity errors surface in-request."""
        self._session.delete(link)
        self._session.flush()
