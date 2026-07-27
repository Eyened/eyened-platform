from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
from fastapi import Depends
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

from ..db import get_db
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import BadRequestError, NotFoundError
from .segmentation_data_store import (
    SegmentationDataStore,
    get_segmentation_data_store,
)


class SegmentationService:
    """Business logic for Segmentation CRUD, binary data, and Tag links.

    Coordinates with an injected ``SegmentationDataStore`` (zarr). Zarr writes
    are NOT part of the DB transaction — store/DB cross-atomicity remains out
    of scope for this refactor (tracked separately: zarr-concurrency /
    segmentation storage-port work). Each site below preserves the exact
    pre-refactor ordering of the store write relative to the DB flush.
    """

    def __init__(
        self,
        repository: SegmentationRepository,
        image_repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        data_store: SegmentationDataStore,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.images = image_repository
        self.tags = tag_repository
        self.store = data_store
        self.audit = audit

    def get_segmentation(self, segmentation_id: int) -> Segmentation:
        """Return a segmentation by id (tag links loaded).

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        item = self.repository.get_with_tag_links(segmentation_id)
        if item is None:
            raise NotFoundError("Segmentation not found")
        return item

    def read_data(
        self,
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
        segmentation = self.repository.get_by_id(segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation data not found")
        try:
            return self.store.read(segmentation, axis=axis, slice_index=scan_nr)
        except ValueError as e:
            raise BadRequestError(str(e)) from e

    def create(
        self,
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
        instance = self.images.get_by_public_id(image_id)
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

        # add+flush assigns the PK; the store write below MUST stay after it
        # (the store keys writes by SegmentationID). Zarr I/O is not part of
        # the DB transaction — see the class-level note on atomicity.
        self.repository.add(segmentation)
        try:
            self.store.write(segmentation, data)
        except ValueError as e:
            raise BadRequestError(str(e)) from e

        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="Segmentation",
                actor=actor,
                entity_id=segmentation.SegmentationID,
                changes={
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
        segmentation = self.repository.get_by_id(segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation data not found")
        # Store write MUST stay before the repo write here (unchanged order
        # from pre-refactor: store.write -> session.add). Zarr I/O is not
        # part of the DB transaction — see the class-level note on atomicity.
        try:
            self.store.write(
                segmentation, data, axis=axis, slice_index=scan_nr
            )
        except (IndexError, ValueError) as e:
            raise BadRequestError(str(e)) from e
        # segmentation is already persistent (fetched via get_by_id above);
        # flush() is the honest name for what's needed here -- add() on an
        # already-tracked instance is a no-op beyond the flush it also does.
        self.repository.flush()
        if self.audit is not None:
            # Pre-refactor log_simple carried no fields/changes (high-frequency
            # op, deliberately lightweight) — preserved as-is.
            self.audit.record(
                action="UPDATE",
                entity="Segmentation",
                actor=actor,
                entity_id=segmentation_id,
            )
        return segmentation

    def soft_delete(self, segmentation_id: int, actor: ActingUser) -> None:
        """Soft-delete a segmentation (sets Inactive; row is kept).

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        segmentation = self.repository.get_by_id(segmentation_id)
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
        self.repository.flush()
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="Segmentation",
                actor=actor,
                entity_id=segmentation_id,
                changes=deleted_data,
            )
        return None

    def patch(
        self,
        segmentation_id: int,
        *,
        reference_segmentation_id: int | None,
        feature_id: int | None,
        threshold: float | None,
        actor: ActingUser,
    ) -> Segmentation:
        """Apply the provided (non-None) fields to a segmentation.

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        segmentation = self.repository.get_by_id(segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")

        if reference_segmentation_id is not None:
            segmentation.ReferenceSegmentationID = reference_segmentation_id
        if feature_id is not None:
            segmentation.FeatureID = feature_id
        if threshold is not None:
            segmentation.Threshold = threshold

        # Derive the scalar diff (true old/new per changed column) while the
        # mutations are still pending — before the repo flush() clears the
        # attribute history. Note: this fixes a pre-refactor quirk where
        # reference_segmentation_id/feature_id were assigned twice, so their
        # hand-built "old -> new" strings actually logged "new -> new";
        # threshold was the only field that logged truthfully. AuditService.diff
        # now reports true old/new for all three fields.
        changes = AuditService.diff(
            segmentation, "ReferenceSegmentationID", "FeatureID", "Threshold"
        )
        self.repository.flush()
        if self.audit is not None:
            self.audit.record(
                action="UPDATE",
                entity="Segmentation",
                actor=actor,
                entity_id=segmentation_id,
                changes=changes if changes else None,
            )
        return segmentation

    def tag(
        self,
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
        segmentation = self.repository.get_by_id(segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")
        tag = self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        if tag.TagType != TagType.Segmentation:
            raise BadRequestError("Tag type must be Segmentation")

        link = self.repository.get_tag_link(tag.TagID, segmentation_id)
        if link is None:
            link = self.repository.add_link(
                tag_id=tag.TagID,
                segmentation_id=segmentation_id,
                creator_id=actor.id,
            )
            if self.audit is not None:
                # SegmentationTagLink has a composite PK, so entity_id is
                # null; fold the composite identity into changes (matches
                # untag's DELETE below), or the audit row is unidentifiable.
                self.audit.record(
                    action="INSERT",
                    entity="SegmentationTagLink",
                    actor=actor,
                    changes={
                        "tag_id": tag.TagID,
                        "segmentation_id": segmentation_id,
                    },
                )

        link.Tag = tag  # avoid a Tag lazy-load at DTO time
        return link

    def untag(
        self,
        segmentation_id: int,
        tag_id: int,
        actor: ActingUser,
    ) -> None:
        """Remove a Tag from a segmentation (idempotent; no error if unlinked).

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        segmentation = self.repository.get_by_id(segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")

        link = self.repository.get_tag_link(tag_id, segmentation_id)
        if link is not None:
            deleted_data = {
                "tag_id": tag_id,
                "segmentation_id": segmentation_id,
                "creator_id": link.CreatorID,
            }
            self.repository.delete_link(link)
            if self.audit is not None:
                self.audit.record(
                    action="DELETE",
                    entity="SegmentationTagLink",
                    actor=actor,
                    changes=deleted_data,
                )
        return None


class ModelSegmentationService:
    """Business logic for ModelSegmentation binary data endpoints.

    No audit: the pre-refactor service never called ``self.logger`` (verified
    against ``git show 967e823``), so no ``AuditService`` is wired here — this
    matches Phase 4c's "ModelSegmentation write has no audit" record.
    """

    def __init__(
        self,
        repository: ModelSegmentationRepository,
        data_store: SegmentationDataStore,
    ) -> None:
        self.repository = repository
        self.store = data_store

    def read_data(
        self,
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
        item = self.repository.get_by_id(model_segmentation_id)
        if item is None:
            raise NotFoundError("ModelSegmentation data not found")
        try:
            return self.store.read(item, axis=axis, slice_index=scan_nr)
        except ValueError as e:
            raise BadRequestError(str(e)) from e

    def write_data(
        self,
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
        item = self.repository.get_by_id(model_segmentation_id)
        if item is None:
            raise NotFoundError("ModelSegmentation data not found")
        # Store write MUST stay before the repo write here (unchanged order
        # from pre-refactor: store.write -> session.add). Zarr I/O is not
        # part of the DB transaction — see the class-level note on atomicity.
        try:
            self.store.write(item, data, axis=axis, slice_index=scan_nr)
        except (IndexError, ValueError) as e:
            raise BadRequestError(str(e)) from e
        self.repository.add_item(item)
        return item


def get_segmentation_service(
    db: Session = Depends(get_db),
) -> SegmentationService:
    """Default SegmentationService wiring for FastAPI ``Depends()``."""
    return SegmentationService(
        SegmentationRepository(db),
        ImageInstanceRepository(db),
        TagRepository(db),
        get_segmentation_data_store(),
        audit=get_audit_service(db),
    )


def get_model_segmentation_service(
    db: Session = Depends(get_db),
) -> ModelSegmentationService:
    """Default ModelSegmentationService wiring for FastAPI ``Depends()``."""
    return ModelSegmentationService(
        ModelSegmentationRepository(db),
        get_segmentation_data_store(),
    )
