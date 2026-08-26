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
from eyened_orm.repositories.task_repository import SubTaskRepository
from eyened_orm.authz.ownership import require_owner, require_owner_or_project_admin
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope

from ..db import get_db
from .access_scope import get_access_scope
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
        subtask_repository: SubTaskRepository,
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.images = image_repository
        self.tags = tag_repository
        self.store = data_store
        self.subtasks = subtask_repository
        self.scope = scope
        self._actor = ActingUser.from_scope(scope)
        self.audit = audit

    def _require_reachable_references(
        self,
        *,
        subtask_id: int | None = None,
        reference_segmentation_id: int | None = None,
    ) -> None:
        """Refuse an id the caller cannot reach, before it is written.

        ``None`` passes through -- it is a legitimate value, not an omission.
        Each id is resolved through a **scoped** lookup, mirroring what
        ``image_id`` already does on this same create path: an id outside the
        caller's reach comes back as ``None`` and is answered exactly as a
        non-existent one is.

        Not a consistency guard: nothing here asks whether the subtask holds
        this image, or whether the reference is of the same feature. Those
        questions were deliberately left open.
        """
        if subtask_id is not None and self.repository.get_subtask(subtask_id) is None:
            raise NotFoundError("SubTask not found")
        if (
            reference_segmentation_id is not None
            and self.repository.get_by_id(reference_segmentation_id) is None
        ):
            raise NotFoundError("Referenced Segmentation not found")

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
        self._require_reachable_references(
            subtask_id=subtask_id,
            reference_segmentation_id=reference_segmentation_id,
        )
        # No ownership overlay on create: the row does not exist yet and its
        # author is the caller by construction (CreatorID below). The floor is
        # judged on the image's project, which is the only project the new
        # segmentation can ever touch.
        self.scope.require(
            self.images.project_ids(instance.ImageInstanceID),
            ProjectRole.grader,
            entity="Segmentation",
            entity_id=None,
        )

        segmentation = Segmentation(
            ImageInstanceID=instance.ImageInstanceID,
            FeatureID=feature_id,
            CreatorID=self.scope.actor_id,
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
        if subtask_id is not None:
            self.subtasks.claim_if_unassigned(subtask_id, self.scope.actor_id)

        if self.audit is not None:
            self.audit.record(
                action="INSERT",
                entity="Segmentation",
                actor=self._actor,
                entity_id=segmentation.SegmentationID,
                changes={
                    "image_instance_id": segmentation.ImageInstanceID,
                    "feature_id": segmentation.FeatureID,
                    "subtask_id": segmentation.SubTaskID,
                    "creator_id": segmentation.CreatorID,
                    "data_type": segmentation.DataType,
                    "data_representation": segmentation.DataRepresentation,
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
    ) -> Segmentation:
        """Write (a slice of) a segmentation's binary data via the store.

        Raises:
            NotFoundError: If the segmentation does not exist.
            BadRequestError: If the store rejects the write.
        """
        segmentation = self.repository.get_by_id(segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation data not found")
        projects = self.repository.project_ids(segmentation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="Segmentation",
            entity_id=segmentation_id,
        )
        require_owner(
            self.scope,
            owner_id=segmentation.CreatorID,
            entity="Segmentation",
            entity_id=segmentation_id,
            projects=projects,
        )
        # Store write MUST stay before the repo write here (unchanged order
        # from pre-refactor: store.write -> session.add). Zarr I/O is not
        # part of the DB transaction — see the class-level note on atomicity.
        try:
            self.store.write(
                segmentation, data, axis=axis, slice_index=scan_nr
            )
        except (IndexError, ValueError) as e:
            raise BadRequestError(str(e)) from e
        self.repository.save(segmentation)
        if self.audit is not None:
            # Pre-refactor log_simple carried no fields/changes (high-frequency
            # op, deliberately lightweight) — preserved as-is.
            self.audit.record(
                action="UPDATE",
                entity="Segmentation",
                actor=self._actor,
                entity_id=segmentation_id,
            )
        return segmentation

    def soft_delete(self, segmentation_id: int) -> None:
        """Soft-delete a segmentation (sets Inactive; row is kept).

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        segmentation = self.repository.get_by_id(segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")
        projects = self.repository.project_ids(segmentation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="Segmentation",
            entity_id=segmentation_id,
        )
        require_owner_or_project_admin(
            self.scope,
            owner_id=segmentation.CreatorID,
            entity="Segmentation",
            entity_id=segmentation_id,
            projects=projects,
        )

        deleted_data = {
            "image_instance_id": segmentation.ImageInstanceID,
            "feature_id": segmentation.FeatureID,
            "subtask_id": segmentation.SubTaskID,
            "creator_id": segmentation.CreatorID,
            "data_type": segmentation.DataType,
            "data_representation": segmentation.DataRepresentation,
            "shape": segmentation.shape,
            "sparse_axis": segmentation.SparseAxis,
            "threshold": segmentation.Threshold,
            "reference_segmentation_id": segmentation.ReferenceSegmentationID,
        }
        segmentation.Inactive = True
        self.repository.save(segmentation)
        if self.audit is not None:
            self.audit.record(
                action="DELETE",
                entity="Segmentation",
                actor=self._actor,
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
    ) -> Segmentation:
        """Apply the provided (non-None) fields to a segmentation.

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        segmentation = self.repository.get_by_id(segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")
        projects = self.repository.project_ids(segmentation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="Segmentation",
            entity_id=segmentation_id,
        )
        require_owner(
            self.scope,
            owner_id=segmentation.CreatorID,
            entity="Segmentation",
            entity_id=segmentation_id,
            projects=projects,
        )

        # After the floor and the overlay, not before: the caller must be
        # entitled to modify this row before the request body is judged at all.
        self._require_reachable_references(
            reference_segmentation_id=reference_segmentation_id
        )

        before = AuditService.snapshot(
            segmentation, "ReferenceSegmentationID", "FeatureID", "Threshold"
        )
        if reference_segmentation_id is not None:
            segmentation.ReferenceSegmentationID = reference_segmentation_id
        if feature_id is not None:
            segmentation.FeatureID = feature_id
        if threshold is not None:
            segmentation.Threshold = threshold

        # Note: this fixes a pre-refactor quirk where reference_segmentation_id
        # /feature_id were assigned twice, so their hand-built "old -> new"
        # strings actually logged "new -> new"; threshold was the only field
        # that logged truthfully. snapshot/diff report true old/new for all three.
        changes = AuditService.diff(before, segmentation)
        self.repository.save(segmentation)
        if self.audit is not None:
            self.audit.record(
                action="UPDATE",
                entity="Segmentation",
                actor=self._actor,
                entity_id=segmentation_id,
                changes=changes if changes else None,
            )
        return segmentation

    def tag(
        self,
        segmentation_id: int,
        tag_id: int,
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
        # A tag link carries no project of its own, so it is authorized against
        # its *parent* -- the deliberate asymmetry recorded at ``PROJECT_IDS_OF``
        # (``projects_of(session, SegmentationTagLink, ...)`` raises by design).
        # The floor therefore names the parent, whose projects it is judged on.
        # It is the only check here: this method discards the client's comment
        # rather than writing it, so there is no rewrite of an existing link
        # for the ownership overlay to guard.
        self.scope.require(
            self.repository.project_ids(segmentation_id),
            ProjectRole.grader,
            entity="Segmentation",
            entity_id=segmentation_id,
        )

        link = self.repository.get_tag_link(tag.TagID, segmentation_id)
        if link is None:
            link = self.repository.add_link(
                tag_id=tag.TagID,
                segmentation_id=segmentation_id,
                creator_id=self.scope.actor_id,
            )
            if self.audit is not None:
                # SegmentationTagLink has a composite PK, so entity_id is
                # null; fold the composite identity into changes (matches
                # untag's DELETE below), or the audit row is unidentifiable.
                self.audit.record(
                    action="INSERT",
                    entity="SegmentationTagLink",
                    actor=self._actor,
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
    ) -> None:
        """Remove a Tag from a segmentation (idempotent; no error if unlinked).

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        segmentation = self.repository.get_by_id(segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation not found")
        projects = self.repository.project_ids(segmentation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="Segmentation",
            entity_id=segmentation_id,
        )

        link = self.repository.get_tag_link(tag_id, segmentation_id)
        if link is not None:
            require_owner_or_project_admin(
                self.scope,
                owner_id=link.CreatorID,
                entity="SegmentationTagLink",
                entity_id=None,
                projects=projects,
            )
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
                    actor=self._actor,
                    changes=deleted_data,
                )
        return None


class ModelSegmentationService:
    """Business logic for ModelSegmentation binary data endpoints.

    The deliberate hole in the ownership overlay. ``ModelSegmentation`` carries
    no ``CreatorID``, so "deny unless ``CreatorID`` is the actor" would match
    nobody and refuse every actor forever — including the grader correcting
    model output on the live endpoint. The write is gated by scope plus
    ``grader`` and nothing else.

    Audit is therefore not optional here but compensatory: because the row
    cannot record who changed it, the ``AuditLog`` row is the only place that
    author exists. (This replaces an earlier "no audit" note, which recorded
    the pre-refactor behaviour that this exemption now has to make good.)
    """

    def __init__(
        self,
        repository: ModelSegmentationRepository,
        data_store: SegmentationDataStore,
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.store = data_store
        self.scope = scope
        self._actor = ActingUser.from_scope(scope)
        self.audit = audit

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
        # Scope plus the grader floor is the whole check: see the class
        # docstring for why no ownership overlay can apply to this entity.
        projects = self.repository.project_ids(model_segmentation_id)
        self.scope.require(
            projects,
            ProjectRole.grader,
            entity="ModelSegmentation",
            entity_id=model_segmentation_id,
        )
        # Store write MUST stay before the repo write here (unchanged order
        # from pre-refactor: store.write -> session.add). Zarr I/O is not
        # part of the DB transaction — see the class-level note on atomicity.
        try:
            self.store.write(item, data, axis=axis, slice_index=scan_nr)
        except (IndexError, ValueError) as e:
            raise BadRequestError(str(e)) from e
        self.repository.save(item)
        if self.audit is not None:
            # A ModelSegmentation resolves through one image to exactly one
            # project, so the set is a singleton.
            self.audit.record(
                action="UPDATE",
                entity="ModelSegmentation",
                actor=self._actor,
                entity_id=model_segmentation_id,
                project_id=next(iter(projects), None),
                changes={"axis": axis, "scan_nr": scan_nr},
            )
        return item


def get_segmentation_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> SegmentationService:
    """Default SegmentationService wiring for FastAPI ``Depends()``."""
    return SegmentationService(
        SegmentationRepository(db, scope=scope),
        ImageInstanceRepository(db, scope=scope),
        TagRepository(db, scope=scope),
        get_segmentation_data_store(),
        SubTaskRepository(db, scope=scope),
        scope=scope,
        audit=get_audit_service(db),
    )


def get_model_segmentation_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> ModelSegmentationService:
    """Default ModelSegmentationService wiring for FastAPI ``Depends()``."""
    return ModelSegmentationService(
        ModelSegmentationRepository(db, scope=scope),
        get_segmentation_data_store(),
        scope=scope,
        audit=get_audit_service(db),
    )
