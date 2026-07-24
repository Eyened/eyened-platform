from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from eyened_orm import ImageInstance, ModelSegmentation, Segmentation
from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.tag import SegmentationTagLink, TagType
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.segmentation_repository import (
    ModelSegmentationRepository,
    SegmentationRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.repositories.task_repository import SubTaskRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import BadRequestError, NotFoundError
from .segmentation_data_store import (
    SegmentationDataStore,
    get_segmentation_data_store,
)


class SegmentationService:
    """Business logic for Segmentation CRUD, binary data, and Tag links."""

    def __init__(
        self,
        repository: SegmentationRepository,
        image_repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        data_store: SegmentationDataStore,
        subtask_repository: SubTaskRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.images = image_repository
        self.tags = tag_repository
        self.store = data_store
        self.subtasks = subtask_repository
        self.logger = logger

    def get_segmentation(
        self, session: Session, segmentation_id: int
    ) -> Segmentation:
        """Return a segmentation by id (tag links loaded).

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        item = self.repository.get_with_tag_links(session, segmentation_id)
        if item is None:
            raise NotFoundError("Segmentation not found")
        return item

    def read_data(
        self,
        session: Session,
        segmentation_id: int,
        *,
        axis: Optional[int] = None,
        scan_nr: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """Return the stored array for a segmentation (None if none stored).

        Raises:
            NotFoundError: If the segmentation does not exist.
            BadRequestError: If the store rejects the read parameters.
        """
        segmentation = self.repository.get_by_id(session, segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation data not found")
        try:
            return self.store.read(segmentation, axis=axis, slice_index=scan_nr)
        except ValueError as e:
            raise BadRequestError(str(e)) from e

    def create(
        self,
        session: Session,
        *,
        image_id: str,
        feature_id: int,
        subtask_id: int | None,
        data_type: Datatype,
        data_representation: DataRepresentation,
        depth: int | None,
        height: int | None,
        width: int | None,
        sparse_axis: int | None,
        image_projection_matrix: list[list[float]] | None,
        scan_indices: list[int] | None,
        threshold: float | None,
        reference_segmentation_id: int | None,
        array: np.ndarray | None,
        actor: ActingUser,
    ) -> Segmentation:
        """Create a Segmentation and write its (empty or provided) data.

        Raises:
            NotFoundError: If image_id resolves to no instance.
            BadRequestError: If the array/shape is inconsistent or the store
                rejects the write.
        """
        instance = self.images.get_by_public_id(session, image_id)
        if instance is None:
            raise NotFoundError("ImageInstance not found")

        segmentation = Segmentation(
            ImageInstanceID=instance.ImageInstanceID,
            FeatureID=feature_id,
            CreatorID=actor.id,
            SubTaskID=subtask_id,
            DataType=data_type,
            DataRepresentation=data_representation,
            Depth=depth,
            Height=height,
            Width=width,
            SparseAxis=sparse_axis,
            ImageProjectionMatrix=image_projection_matrix,
            ScanIndices=scan_indices,
            Threshold=threshold,
            ReferenceSegmentationID=reference_segmentation_id,
            DateInserted=datetime.now(),
        )
        data = self._assemble_data(segmentation, instance, array)

        session.add(segmentation)
        session.flush()
        try:
            self.store.write(segmentation, data)
        except ValueError as e:
            raise BadRequestError(str(e)) from e
        if subtask_id is not None:
            self.subtasks.claim_if_unassigned(session, subtask_id, actor.id)
        session.commit()
        session.refresh(segmentation)

        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint="POST /api/segmentations",
                entity="Segmentation",
                entity_id=segmentation.SegmentationID,
                fields={
                    "image_instance_id": segmentation.ImageInstanceID,
                    "feature_id": segmentation.FeatureID,
                    "subtask_id": segmentation.SubTaskID,
                    "creator_id": segmentation.CreatorID,
                    "data_type": str(segmentation.DataType),
                    "data_representation": str(segmentation.DataRepresentation),
                    "shape": segmentation.shape,
                    "sparse_axis": segmentation.SparseAxis,
                    "threshold": segmentation.Threshold,
                    "reference_segmentation_id": (
                        segmentation.ReferenceSegmentationID
                    ),
                },
            )
        return segmentation

    def _assemble_data(
        self,
        segmentation: Segmentation,
        image: ImageInstance,
        array: Optional[np.ndarray],
    ) -> np.ndarray:
        """Build the data volume to store, validating array vs. segmentation.

        Reproduces the pre-refactor route logic; raises BadRequestError on any
        shape inconsistency.
        """
        if array is None:
            return self._create_empty_array(segmentation, image)

        if segmentation.ScanIndices is None:
            data = array
            if segmentation.shape != array.shape:
                raise BadRequestError(
                    f"Segmentation shape {segmentation.shape} does not match "
                    f"array shape {array.shape}"
                )
        else:
            if segmentation.SparseAxis is None:
                raise BadRequestError("SparseAxis is not set for sparse volume")
            if len(segmentation.ScanIndices) != array.shape[
                segmentation.SparseAxis
            ]:
                raise BadRequestError(
                    f"ScanIndices length {len(segmentation.ScanIndices)} does "
                    f"not match array sparse axis length "
                    f"{array.shape[segmentation.SparseAxis]}"
                )
            data = np.zeros(segmentation.shape, dtype=segmentation.dtype)
            for i, scan_index in enumerate(segmentation.ScanIndices):
                data[scan_index] = array[i]

        for dim, attr in zip(data.shape, ["Depth", "Height", "Width"]):
            val = getattr(segmentation, attr)
            if val is None:
                setattr(segmentation, attr, dim)
            elif val != dim:
                raise BadRequestError(
                    f"Segmentation {attr} ({val}) does not match array "
                    f"{attr} ({dim})"
                )
        return data

    def _create_empty_array(
        self, segmentation: Segmentation, image: ImageInstance
    ) -> np.ndarray:
        """Zeros volume sized from the segmentation (falling back to image dims)."""
        s_d, s_h, s_w = segmentation.shape
        im_d, im_h, im_w = image.shape
        shape = (s_d or im_d, s_h or im_h, s_w or im_w)
        segmentation.Depth, segmentation.Height, segmentation.Width = shape
        return np.zeros(shape, dtype=segmentation.dtype)

    def write_data(
        self,
        session: Session,
        segmentation_id: int,
        data: np.ndarray,
        *,
        axis: Optional[int] = None,
        scan_nr: Optional[int] = None,
        actor: ActingUser,
    ) -> Segmentation:
        """Write (a slice of) a segmentation's binary data via the store.

        Raises:
            NotFoundError: If the segmentation does not exist.
            BadRequestError: If the store rejects the write.
        """
        segmentation = self.repository.get_by_id(session, segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation data not found")
        try:
            self.store.write(
                segmentation, data, axis=axis, slice_index=scan_nr
            )
        except (IndexError, ValueError) as e:
            raise BadRequestError(str(e)) from e
        session.add(segmentation)
        session.commit()
        session.refresh(segmentation)
        if self.logger is not None:
            self.logger.log_simple(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PUT /api/segmentations/{segmentation_id}/data",
                operation="UPDATE",
                entity="Segmentation",
                entity_id=segmentation_id,
            )
        return segmentation

    def soft_delete(
        self, session: Session, segmentation_id: int, actor: ActingUser
    ) -> None:
        """Soft-delete a segmentation (sets Inactive; row is kept).

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        segmentation = self.repository.get_by_id(session, segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")

        deleted_data = {
            "image_instance_id": segmentation.ImageInstanceID,
            "feature_id": segmentation.FeatureID,
            "subtask_id": segmentation.SubTaskID,
            "creator_id": segmentation.CreatorID,
            "data_type": str(segmentation.DataType),
            "data_representation": str(segmentation.DataRepresentation),
            "shape": segmentation.shape,
            "sparse_axis": segmentation.SparseAxis,
            "threshold": segmentation.Threshold,
            "reference_segmentation_id": segmentation.ReferenceSegmentationID,
        }
        segmentation.Inactive = True
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/segmentations/{segmentation_id}",
                entity="Segmentation",
                entity_id=segmentation_id,
                deleted_data=deleted_data,
            )
        return None

    def patch(
        self,
        session: Session,
        segmentation_id: int,
        *,
        reference_segmentation_id: int | None,
        feature_id: int | None,
        threshold: float | None,
        actor: ActingUser,
    ) -> Segmentation:
        """Apply the provided (non-None) fields to a segmentation.

        Preserves the pre-refactor audit quirk: reference/feature are applied
        before the change-string is built, so they log ``<new> -> <new>`` while
        threshold logs the true ``<old> -> <new>``. Audit-log-only; not an API
        field. See deferred findings.

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        segmentation = self.repository.get_by_id(session, segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")

        if reference_segmentation_id is not None:
            segmentation.ReferenceSegmentationID = reference_segmentation_id
        if feature_id is not None:
            segmentation.FeatureID = feature_id
        changes: dict[str, str] = {}
        if reference_segmentation_id is not None:
            changes["reference_segmentation_id"] = (
                f"{segmentation.ReferenceSegmentationID} -> "
                f"{reference_segmentation_id}"
            )
            segmentation.ReferenceSegmentationID = reference_segmentation_id
        if feature_id is not None:
            changes["feature_id"] = f"{segmentation.FeatureID} -> {feature_id}"
            segmentation.FeatureID = feature_id
        if threshold is not None:
            changes["threshold"] = f"{segmentation.Threshold} -> {threshold}"
            segmentation.Threshold = threshold

        session.commit()
        session.refresh(segmentation)
        if self.logger is not None:
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/segmentations/{segmentation_id}",
                entity="Segmentation",
                entity_id=segmentation_id,
                changes=changes if changes else None,
            )
        return segmentation

    def tag(
        self,
        session: Session,
        segmentation_id: int,
        tag_id: int,
        actor: ActingUser,
    ) -> SegmentationTagLink:
        """Attach a Tag to a segmentation (idempotent).

        Behavior-preserving: the client-supplied comment is NOT stored (matches
        the pre-refactor handler). See deferred findings.

        Raises:
            NotFoundError: If the segmentation or the tag does not exist.
            BadRequestError: If the tag is not a Segmentation-type tag.
        """
        segmentation = self.repository.get_by_id(session, segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")
        tag = self.tags.get_by_id(session, tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.Segmentation:
            raise BadRequestError("Tag type must be Segmentation")

        link = self.repository.get_tag_link(session, tag.TagID, segmentation_id)
        if link is None:
            link = SegmentationTagLink(
                TagID=tag.TagID,
                SegmentationID=segmentation_id,
                CreatorID=actor.id,
            )
            session.add(link)
            session.commit()
            session.refresh(link)
            if self.logger is not None:
                self.logger.log_insert(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=f"POST /api/segmentations/{segmentation_id}/tags",
                    entity="SegmentationTagLink",
                    fields={
                        "tag_id": tag.TagID,
                        "segmentation_id": segmentation_id,
                    },
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def untag(
        self,
        session: Session,
        segmentation_id: int,
        tag_id: int,
        actor: ActingUser,
    ) -> None:
        """Remove a Tag from a segmentation (idempotent; no error if unlinked).

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        segmentation = self.repository.get_by_id(session, segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")

        link = self.repository.get_tag_link(session, tag_id, segmentation_id)
        if link is not None:
            deleted_data = {
                "tag_id": tag_id,
                "segmentation_id": segmentation_id,
                "creator_id": link.CreatorID,
            }
            session.delete(link)
            session.commit()
            if self.logger is not None:
                self.logger.log_delete(
                    user=actor.username,
                    user_id=actor.id,
                    endpoint=(
                        f"DELETE /api/segmentations/{segmentation_id}"
                        f"/tags/{tag_id}"
                    ),
                    entity="SegmentationTagLink",
                    fields={"tag_id": tag_id, "segmentation_id": segmentation_id},
                    deleted_data=deleted_data,
                )
        return None


class ModelSegmentationService:
    """Business logic for ModelSegmentation binary data endpoints."""

    def __init__(
        self,
        repository: ModelSegmentationRepository,
        data_store: SegmentationDataStore,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.store = data_store
        self.logger = logger

    def read_data(
        self,
        session: Session,
        model_segmentation_id: int,
        *,
        axis: Optional[int] = None,
        scan_nr: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """Return the stored array for a model segmentation (None if none).

        Raises:
            NotFoundError: If the model segmentation does not exist.
            BadRequestError: If the store rejects the read parameters.
        """
        item = self.repository.get_by_id(session, model_segmentation_id)
        if item is None:
            raise NotFoundError("ModelSegmentation data not found")
        try:
            return self.store.read(item, axis=axis, slice_index=scan_nr)
        except ValueError as e:
            raise BadRequestError(str(e)) from e

    def write_data(
        self,
        session: Session,
        model_segmentation_id: int,
        data: np.ndarray,
        *,
        axis: Optional[int] = None,
        scan_nr: Optional[int] = None,
    ) -> ModelSegmentation:
        """Write (a slice of) a model segmentation's binary data via the store.

        Raises:
            NotFoundError: If the model segmentation does not exist.
            BadRequestError: If the store rejects the write.
        """
        item = self.repository.get_by_id(session, model_segmentation_id)
        if item is None:
            raise NotFoundError("ModelSegmentation data not found")
        try:
            self.store.write(item, data, axis=axis, slice_index=scan_nr)
        except (IndexError, ValueError) as e:
            raise BadRequestError(str(e)) from e
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


def get_segmentation_service() -> SegmentationService:
    """Default SegmentationService wiring for FastAPI ``Depends()``."""
    return SegmentationService(
        SegmentationRepository(),
        ImageInstanceRepository(),
        TagRepository(),
        get_segmentation_data_store(),
        SubTaskRepository(),
        logger=get_db_logger(),
    )


def get_model_segmentation_service() -> ModelSegmentationService:
    """Default ModelSegmentationService wiring for FastAPI ``Depends()``."""
    return ModelSegmentationService(
        ModelSegmentationRepository(),
        get_segmentation_data_store(),
        logger=get_db_logger(),
    )
