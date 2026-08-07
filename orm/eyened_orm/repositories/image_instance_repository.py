from __future__ import annotations

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
from eyened_orm.authz.scope import AccessScope

from ._scoped import scoped_one

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

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

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
        return scoped_one(
            self._session,
            ImageInstance,
            self._scope,
            ImageInstance.ImageInstanceID == instance_id,
            options=tuple(opts),
        )

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
        item = scoped_one(
            self._session,
            ImageInstance,
            self._scope,
            ImageInstance.PublicID == image_id,
            options=tuple(opts),
        )
        if item is None and image_id.isdigit():
            # The numeric-PK fallback is a second lookup, so it needs the filter
            # too -- an unscoped fallback would be a read bypass reachable by
            # simply passing the integer id as a string.
            item = scoped_one(
                self._session,
                ImageInstance,
                self._scope,
                ImageInstance.ImageInstanceID == int(image_id),
                options=tuple(opts),
            )
        return item

    def get_with_storage_by_public_id(
        self, public_id: str
    ) -> ImageInstance | None:
        """Return the instance by PublicID with storage loaded (PK fallback), or None.

        Mirrors the legacy ``_get_image_instance_by_public_id`` resolver: try the
        PublicID; on no match fall back to the raw id (numeric-PK fallback).
        """
        item = scoped_one(
            self._session,
            ImageInstance,
            self._scope,
            ImageInstance.PublicID == public_id,
            options=(_STORAGE_LOADER,),
        )
        if item is None and public_id.isdigit():
            item = scoped_one(
                self._session,
                ImageInstance,
                self._scope,
                ImageInstance.ImageInstanceID == int(public_id),
                options=(_STORAGE_LOADER,),
            )
        return item

    def get_tag_link(
        self, tag_id: int, image_instance_id: int
    ) -> ImageInstanceTagLink | None:
        """Return the link for (tag_id, image_instance_id), or None if absent/out of scope."""
        return scoped_one(
            self._session,
            ImageInstanceTagLink,
            self._scope,
            ImageInstanceTagLink.TagID == tag_id,
            ImageInstanceTagLink.ImageInstanceID == image_instance_id,
        )

    def save_link(self, link: ImageInstanceTagLink) -> None:
        """Persist in-place mutations to ``link`` (e.g. ``Comment``) within the
        request transaction.

        ``link`` names what is being saved; the flush covers the whole unit of
        work, deliberately not just this row.
        """
        self._session.flush()

    def get_by_public_id(self, public_id: str) -> ImageInstance | None:
        """Return the instance with this PublicID (no eager loads), or None.

        Plain PublicID resolver used to map an external image id to its row —
        the faithful equivalent of the legacy ``_resolve_image_instance_id``
        helper (no PK/digit fallback, unlike ``get_full_graph_by_public_id``).
        """
        return scoped_one(
            self._session,
            ImageInstance,
            self._scope,
            ImageInstance.PublicID == public_id,
        )

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
        """Delete an ImageInstanceTagLink and flush within the request transaction."""
        self._session.delete(link)
        self._session.flush()
