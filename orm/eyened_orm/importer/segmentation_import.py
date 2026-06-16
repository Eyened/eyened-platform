"""Stage-2 segmentation import: ``SegmentationImport`` → ``plan_import`` + zarr write."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import Creator, Feature, ImageInstance, Segmentation
from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.segmentation_storage import write_segmentation_data

from .import_run import ImportRun
from .importer import plan_import
from .importer_dtos import ImportSegmentationRow, SegmentationImport
from .importer_mappings_segmentation import SEGMENTATION_ENTITY_SPECS


def ensure_dhw(array: np.ndarray) -> np.ndarray:
    if array.ndim == 2:
        return array[np.newaxis, ...]
    if array.ndim == 3:
        return array
    raise ValueError(f"segmentation mask must be 2D or 3D, got shape {array.shape}")


def segmentation_import_to_row(
    image_instance_id: int,
    seg: SegmentationImport,
) -> ImportSegmentationRow:
    if not seg.feature_name or not seg.creator_name:
        raise ValueError("feature_name and creator_name are required")

    data = ensure_dhw(seg.data)
    d, h, w = (int(x) for x in data.shape)

    return ImportSegmentationRow(
        image_instance_id=image_instance_id,
        feature_name=seg.feature_name,
        creator_name=seg.creator_name,
        depth=seg.depth or d,
        height=seg.height or h,
        width=seg.width or w,
        sparse_axis=0 if seg.sparse_axis is None else seg.sparse_axis,
        data_representation=seg.data_representation or DataRepresentation.Binary,
        data_type=seg.data_type or Segmentation.infer_data_type(data),
        threshold=seg.threshold,
        image_projection_matrix=seg.image_projection_matrix,
        scan_indices=seg.scan_indices,
        reference_segmentation_id=seg.reference_segmentation_id,
    )


def _find_segmentation(
    session: Session,
    image_instance_id: int,
    feature_name: str,
    creator_name: str,
) -> Segmentation | None:
    feature = Feature.by_column(session, FeatureName=feature_name)
    creator = Creator.by_column(session, CreatorName=creator_name)
    if feature is None or creator is None:
        return None
    return session.scalar(
        select(Segmentation)
        .where(
            Segmentation.ImageInstanceID == image_instance_id,
            Segmentation.FeatureID == feature.FeatureID,
            Segmentation.CreatorID == creator.CreatorID,
            Segmentation.Inactive == False,  # noqa: E712
        )
        .order_by(Segmentation.SegmentationID.desc())
        .limit(1)
    )


def plan_segmentation_import(
    session: Session,
    image_instance_id: int,
    segmentations: Sequence[SegmentationImport],
    *,
    commit: bool = False,
    write_mask_data: bool = True,
) -> ImportRun:
    """Plan metadata via importer, apply, then write each ``SegmentationImport.data`` to zarr."""
    if not segmentations:
        return ImportRun(session=session)

    image = session.get(ImageInstance, image_instance_id)
    if image is None:
        raise ValueError(f"ImageInstance {image_instance_id} not found")

    rows = [segmentation_import_to_row(image_instance_id, s) for s in segmentations]
    run = plan_import(session, rows, entity_specs=SEGMENTATION_ENTITY_SPECS)
    run.apply()
    session.flush()

    if write_mask_data:
        for row, seg in zip(rows, segmentations, strict=True):
            orm_seg = _find_segmentation(
                session,
                row.image_instance_id,
                row.feature_name,
                row.creator_name,
            )
            if orm_seg is None:
                raise RuntimeError(
                    f"Segmentation not found after import: "
                    f"image={row.image_instance_id} "
                    f"feature={row.feature_name!r} creator={row.creator_name!r}"
                )
            if orm_seg.ImageInstance is None:
                orm_seg.ImageInstance = image
            write_segmentation_data(orm_seg, ensure_dhw(seg.data))

    if commit:
        session.commit()
    return run
