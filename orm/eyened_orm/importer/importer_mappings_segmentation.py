from __future__ import annotations

from eyened_orm import Segmentation

from .importer_mappings_base import CREATOR, FEATURE, Entity, key, lookup, req

SEGMENTATION = Entity(
    model=Segmentation,
    pk_column="SegmentationID",
    pk_row_field="segmentation_id",
    lookups=(
        lookup(
            key("ImageInstanceID"),
            key("FeatureID", FEATURE),
            key("CreatorID", CREATOR),
        ),
    ),
    implies=(
        req(CREATOR, "Creator"),
        req(FEATURE, "Feature"),
    ),
    fields={
        "ImageInstanceID": "image_instance_id",
        "Depth": "depth",
        "Height": "height",
        "Width": "width",
        "SparseAxis": "sparse_axis",
        "DataRepresentation": "data_representation",
        "DataType": "data_type",
        "Threshold": "threshold",
        "ImageProjectionMatrix": "image_projection_matrix",
        "ScanIndices": "scan_indices",
        "ReferenceSegmentationID": "reference_segmentation_id",
        "Inactive": "inactive",
        "SubTaskID": "subtask_id",
    },
    non_mutable=frozenset({"Depth", "Height", "Width"}),
)

SEGMENTATION_ENTITY_SPECS = (
    CREATOR,
    FEATURE,
    SEGMENTATION,
)
