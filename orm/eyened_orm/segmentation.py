from datetime import datetime
from enum import Enum
import gzip
import io
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Set

import numpy as np
from eyened_orm.api_client import get_api_client
from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint, event, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, object_session, relationship

from .attribute_value_lookup_mixin import AttributeValueLookupMixin
from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (
        AttributeValue,
        Creator,
        Feature,
        ImageInstance,
        SegmentationTagLink,
        SubTask,
    )


class ModelKind(Enum):
    Segmentation = "segmentation"
    Attributes = "attributes"


class DataRepresentation(Enum):
    # 0 = background, >0 = foreground
    Binary = "Binary"

    # A binary mask with two channels packed into a single byte.
    # Bit 0 = mask; Bit 1 = questionable/uncertain.
    # 0 = background, 1 is drawing, 2 = questionable/uncertain, 3 = drawing + questionable/uncertain
    DualBitMask = "DualBitMask"

    # Per-pixel float mask (soft segmentation, probability map)
    Probability = "Probability"

    # Multi-label segmentation — each bit in an integer represents a label.
    # For example:
    #   0x00 => 00000000 => background
    #   0x01 => 00000001 => feature 1 present
    #   0x02 => 00000010 => feature 2 present
    #   0x04 => 00000100 => feature 3 present
    #   0x03 => 00000011 => feature 1 + feature 2 present
    MultiLabel = "MultiLabel"

    # Multi-class segmentation — each voxel/pixel is assigned exactly one class.
    # For example:
    #   0 = background
    #   1 = ILM
    #   2 = GCL
    #   3 = IPL
    #   ...
    MultiClass = "MultiClass"


class Datatype(Enum):
    R8 = "R8"  # 8-bit unsigned integer, interpreted as [0, 1]
    R8UI = "R8UI"  # 8-bit unsigned integer
    R16UI = "R16UI"  # 16-bit unsigned integer
    R32UI = "R32UI"  # 32-bit unsigned integer
    R32F = "R32F"  # 32-bit float


class SegmentationBase(AttributeValueLookupMixin, Base):
    __abstract__ = True  # This makes the class abstract

    # index in the zarr array of the segmentation
    ZarrArrayIndex: Mapped[Optional[int]]

    # image instance that the segmentation is associated with
    ImageInstanceID: Mapped[int] = mapped_column(
        ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE")
    )

    DataRepresentation: Mapped[DataRepresentation] = mapped_column(
        SAEnum(DataRepresentation)
    )

    # shape of the segmentation
    Depth: Mapped[int]
    Height: Mapped[int]
    Width: Mapped[int]

    # indicates the axis along which the segmentation is sparse
    # axis 0 = depth, axis 1 = height, axis 2 = width
    SparseAxis: Mapped[Optional[int]]

    # Matrix that projects the segmentation to image space (along the sparse axis)
    # If None, the shape of the segmentation must match the shape of the image instance
    ImageProjectionMatrix: Mapped[Optional[List[List[float]]]] = mapped_column(JSON)

    # indices with valid segmentation data along the sparse axis
    # If None, the segmentation is dense (i.e valid for all ScanIndices)
    ScanIndices: Mapped[Optional[List[int]]] = mapped_column(JSON)

    DataType: Mapped[Datatype] = mapped_column(SAEnum(Datatype))

    Threshold: Mapped[Optional[float]]

    @property
    def dtype(self) -> np.dtype:
        if self.DataType == Datatype.R8:
            return np.dtype(np.uint8)
        elif self.DataType == Datatype.R8UI:
            return np.dtype(np.uint8)
        elif self.DataType == Datatype.R16UI:
            return np.dtype(np.uint16)
        elif self.DataType == Datatype.R32UI:
            return np.dtype(np.uint32)
        elif self.DataType == Datatype.R32F:
            return np.dtype(np.float32)
        else:
            raise ValueError(f"Unsupported data type: {self.DataType}")

    @property
    def shape(self) -> tuple[int, int, int]:
        return (self.Depth, self.Height, self.Width)

    @property
    def is_3d(self) -> bool:
        # all axes must be > 1 in length
        return self.Height > 1 and self.Width > 1 and self.Depth > 1

    @property
    def is_2d(self) -> bool:
        return not self.is_3d

    @property
    def is_sparse(self) -> bool:
        return self.SparseAxis is not None

    @property
    def groupname(self) -> str:
        return str(self.DataRepresentation)

    @property
    def projection_matrix(self) -> Optional[np.ndarray]:
        """3x3 transformation matrix from segmentation space to original image space"""
        if self.ImageProjectionMatrix is None:
            return None
        return np.array(self.ImageProjectionMatrix)

    @property
    def projection_matrix_inverse(self) -> Optional[np.ndarray]:
        """3x3 transformation matrix from original image space to segmentation space"""
        if self.ImageProjectionMatrix is None:
            return None
        return np.linalg.inv(np.array(self.ImageProjectionMatrix))

    def _api_data_path(self) -> str:
        seg_id = getattr(self, "SegmentationID", None)
        if seg_id is not None:
            return f"/api/segmentations/{seg_id}/data"

        model_seg_id = getattr(self, "ModelSegmentationID", None)
        if model_seg_id is not None:
            return f"/api/model-segmentations/{model_seg_id}/data"

        raise ValueError(
            "Segmentation must be persisted before reading or writing data"
        )

    def write_data(
        self,
        data: np.ndarray,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ) -> int:
        """Write annotation data (D, H, W) through the API."""

        if not self.ImageInstance:
            raise ValueError("Segmentation has no associated ImageInstance")

        client = get_api_client()
        params = None
        if axis is not None or slice_index is not None:
            params = {"axis": axis, "scan_nr": slice_index}

        np_buf = io.BytesIO()
        np.save(np_buf, data)
        payload = np_buf.getvalue()

        resp = client.put(
            self._api_data_path(),
            params=params,
            headers={"Content-Type": "application/octet-stream"},
            data=payload,
        )
        resp.raise_for_status()

        zarr_index = self.ZarrArrayIndex
        try:
            body = resp.json()
            if isinstance(body, dict):
                if "ZarrArrayIndex" in body:
                    zarr_index = body["ZarrArrayIndex"]
                elif "zarr_array_index" in body:
                    zarr_index = body["zarr_array_index"]
        except ValueError:
            pass

        # for sparse annotations, we need to update the ScanIndices list
        if self.ScanIndices is not None and self.is_sparse and axis == self.SparseAxis:
            if slice_index not in self.ScanIndices:
                # copy necessary to ensure update is picked up by the ORM
                scan_indices = self.ScanIndices.copy()
                scan_indices.append(slice_index)
                self.ScanIndices = scan_indices

        self.ZarrArrayIndex = zarr_index
        return zarr_index

    def write_empty(
        self, axis: Optional[int] = None, slice_index: Optional[int] = None
    ) -> int:
        """Write an empty segmentation to the zarr array and update the ZarrArrayIndex."""
        return self.write_data(
            np.zeros(self.shape, dtype=self.dtype), axis, slice_index
        )

    def read_data(
        self, axis: Optional[int] = None, slice_index: Optional[int] = None
    ) -> Optional[np.ndarray]:
        if self.ZarrArrayIndex is None:
            return None

        if not self.ImageInstance:
            raise ValueError("Segmentation has no associated ImageInstance")

        client = get_api_client()
        params = None
        if axis is not None or slice_index is not None:
            params = {"axis": axis, "scan_nr": slice_index}

        resp = client.get(self._api_data_path(), params=params)
        if resp.status_code == 204:
            return None
        resp.raise_for_status()

        raw = resp.content
        return np.load(io.BytesIO(raw), allow_pickle=False)

    @property
    def binary_mask(self) -> np.ndarray | None:
        """
        Return a boolean segmentation mask.

        Notes:
        - Stored segmentation data is always shaped (Depth, Height, Width).
        - For 2D segmentations (i.e. any singleton axis), we automatically drop
          singleton axes and return the squeezed mask.
        - For 3D segmentations, this returns the full 3D volume.
        """
        if (
            self.DataRepresentation == DataRepresentation.MultiClass
            or self.DataRepresentation == DataRepresentation.MultiLabel
        ):
            raise ValueError(
                "MultiClass and MultiLabel data representations are not supported for binary masks"
            )

        data = self.read_data()
        if data is None:
            return None

        if self.DataRepresentation == DataRepresentation.Binary:
            mask = data > 0
        elif self.DataRepresentation == DataRepresentation.DualBitMask:
            mask = (data & 1) > 0
        elif self.DataRepresentation == DataRepresentation.Probability:
            threshold = self.Threshold or 0
            if self.DataType in (Datatype.R8, Datatype.R8UI):
                mask = data > 255 * threshold
            elif self.DataType == Datatype.R32F:
                mask = data > threshold
            else:
                raise ValueError(f"Unsupported data type: {self.DataType}")
        else:
            raise ValueError(
                f"Unsupported data representation: {self.DataRepresentation}"
            )

        # Convenience: for "2D" segmentations (any singleton axis), return the squeezed mask.
        # Examples:
        #   (1, H, W) -> (H, W)
        #   (D, 1, W) -> (D, W)
        #   (D, H, 1) -> (D, H)
        if mask.ndim == 3 and self.is_2d:
            singleton_axes = tuple(i for i, s in enumerate(mask.shape) if s == 1)
            assert len(singleton_axes) == 1, "Expected exactly one singleton axis"
            if singleton_axes:
                mask = np.squeeze(mask, axis=singleton_axes)

        # If a reference segmentation is provided, that is interpreted as a conditional mask
        # i.e. the final mask is the intersection of the current mask and the reference mask.
        if hasattr(self, "ReferenceSegmentation") and self.ReferenceSegmentation:
            reference_mask = self.ReferenceSegmentation.binary_mask
            if reference_mask is not None:
                mask = mask & reference_mask

        return mask

    @property
    def shape_matches_image_shape(self):
        image_shape = self.ImageInstance.shape
        annotation_shape = self.shape
        for i, (x, y) in enumerate(zip(image_shape, annotation_shape)):
            if i != self.l1_axis and x != y:
                return False
        return True

    def check_consistency(self):
        """
        Checks if the segmentation is consistent with the associated ImageInstance
        and ReferenceSegmentation according to the rules.
        """
        # 1. Get ImageInstance
        image = self.ImageInstance
        if not image and self.ImageInstanceID:
            session = object_session(self)
            if session:
                from eyened_orm.image_instance import ImageInstance

                image = session.get(ImageInstance, self.ImageInstanceID)

        if not image:
            # If we can't find the image, we can't check (e.g. detached object without ID)
            # For strict safety, raise error if ID is present but image not found.
            if self.ImageInstanceID:
                # This might happen if we are inserting a new Segmentation and a new ImageInstance together and flush hasn't happened for ImageInstance?
                # But ImageInstanceID is required.
                pass
            return

        # Image dimensions
        # Note: ImageInstance.NrOfFrames can be None (implies 1)
        img_d = image.NrOfFrames if image.NrOfFrames is not None else 1
        img_h = image.Rows_y
        img_w = image.Columns_x

        # 2. Check Dimensions
        if self.ImageProjectionMatrix is None:
            # Strict match
            if self.Depth != img_d and self.SparseAxis != 0:
                raise ValueError(
                    f"Depth mismatch: Segmentation {self.Depth} != Image {img_d}"
                )
            if self.Height != img_h and self.SparseAxis != 1:
                raise ValueError(
                    f"Height mismatch: Segmentation {self.Height} != Image {img_h}"
                )
            if self.Width != img_w and self.SparseAxis != 2:
                raise ValueError(
                    f"Width mismatch: Segmentation {self.Width} != Image {img_w}"
                )
        else:
            # Sparse / Projected
            if self.SparseAxis not in (0, 1, 2):
                raise ValueError(
                    "SparseAxis must be 0, 1, or 2 when ImageProjectionMatrix is provided"
                )

            # Check the sparse axis dimension
            # The dimension along SparseAxis must be equal to image dimension OR 1
            if self.SparseAxis == 0:
                if self.Depth != img_d and self.Depth != 1:
                    raise ValueError(
                        f"Sparse Depth mismatch: {self.Depth} != {img_d} and != 1"
                    )
            elif self.SparseAxis == 1:
                if self.Height != img_h and self.Height != 1:
                    raise ValueError(
                        f"Sparse Height mismatch: {self.Height} != {img_h} and != 1"
                    )
            elif self.SparseAxis == 2:
                if self.Width != img_w and self.Width != 1:
                    raise ValueError(
                        f"Sparse Width mismatch: {self.Width} != {img_w} and != 1"
                    )

        # 3. Check ScanIndices
        if self.ScanIndices is not None:
            if self.SparseAxis is None:
                raise ValueError("ScanIndices provided but SparseAxis is None")

            limit = 0
            if self.SparseAxis == 0:
                limit = img_d
            elif self.SparseAxis == 1:
                limit = img_h
            elif self.SparseAxis == 2:
                limit = img_w

            # indices must be < limit
            for idx in self.ScanIndices:
                if idx >= limit:
                    raise ValueError(
                        f"ScanIndex {idx} out of bounds for axis {self.SparseAxis} (limit {limit})"
                    )

        # 4. Check Reference Segmentation
        if hasattr(self, "ReferenceSegmentationID") and self.ReferenceSegmentationID is not None:
            # We need to fetch the reference.
            # Since SegmentationBase defines the ID but not the relationship in all subclasses,
            # we might need to query safely.
            # Assuming we are in a session
            session = object_session(self)
            if session:
                # Use the class of the reference, which is Segmentation (manual)
                from eyened_orm.segmentation import Segmentation as ManualSegmentation

                ref = session.get(ManualSegmentation, self.ReferenceSegmentationID)
                if ref:
                    if (self.Depth, self.Height, self.Width) != (
                        ref.Depth,
                        ref.Height,
                        ref.Width,
                    ):
                        raise ValueError(
                            f"Dimensions mismatch with ReferenceSegmentation: {self.shape} != {ref.shape}"
                        )


class Segmentation(SegmentationBase):
    __tablename__ = "Segmentation"
    __table_args__ = (
        Index(
            "ix_Segmentation_Image_Feature_Inactive",
            "ImageInstanceID",
            "FeatureID",
            "Inactive",
        ),
        Index("ix_Segmentation_SubTask_Feature", "SubTaskID", "FeatureID"),
        Index("ix_Segmentation_Feature_Inactive", "FeatureID", "Inactive"),
    )
    SegmentationID: Mapped[int] = mapped_column(primary_key=True)

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    FeatureID: Mapped[int] = mapped_column(
        ForeignKey("Feature.FeatureID", ondelete="RESTRICT")
    )
    SubTaskID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("SubTask.SubTaskID", ondelete="SET NULL")
    )

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())
    DateModified: Mapped[Optional[datetime]]

    ReferenceSegmentationID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Segmentation.SegmentationID")
    )

    Inactive: Mapped[bool] = mapped_column(default=False)

    ImageInstance: Mapped["ImageInstance"] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="Segmentations"
    )
    Creator: Mapped["Creator"] = relationship(
        "eyened_orm.creator.Creator", back_populates="Segmentations", lazy="selectin"
    )
    Feature: Mapped["Feature"] = relationship(
        "eyened_orm.segmentation.Feature",
        back_populates="Segmentations",
        lazy="selectin",
    )
    SubTask: Mapped[Optional["SubTask"]] = relationship(
        "eyened_orm.task.SubTask", back_populates="Segmentations"
    )
    SegmentationTagLinks: Mapped[Set["SegmentationTagLink"]] = relationship(
        "eyened_orm.tag.SegmentationTagLink",
        back_populates="Segmentation",
        lazy="selectin",
    )
    AttributeValues: Mapped[List["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue",
        back_populates="Segmentation",
        lazy="selectin",
    )

    ReferenceSegmentation: Mapped[Optional["Segmentation"]] = relationship(
        "Segmentation",
        remote_side="Segmentation.SegmentationID",
        back_populates="ReferenceSegmentations",
        lazy="selectin",
    )

    ReferenceSegmentations: Mapped[list["Segmentation"]] = relationship(
        "Segmentation",
        back_populates="ReferenceSegmentation",
        lazy="selectin",
    )

    @staticmethod
    def infer_data_type(data: np.ndarray) -> Datatype:
        if data.dtype == np.uint8:
            return Datatype.R8UI # or R8?
        if data.dtype == np.uint16:
            return Datatype.R16UI
        if data.dtype == np.uint32:
            return Datatype.R32UI
        if data.dtype == np.float32:
            return Datatype.R32F
        return Datatype.R8

    def make_tag(
        self,
        tag_name: str,
        creator_name: str,
        comment: Optional[str] = None,
        tag_description: Optional[str] = None,
    ) -> "SegmentationTagLink":
        """Create or reuse a tag and link it to this segmentation."""
        from eyened_orm import Creator, Tag, TagType
        from eyened_orm.tag import SegmentationTagLink

        session = self.session
        tag_type = TagType.Segmentation

        # Get or create creator
        creator = Creator.by_name(session, creator_name)
        if creator is None:
            creator = Creator(CreatorName=creator_name, IsHuman=True)
            session.add(creator)
            session.flush()

        # Get or create tag
        tag = Tag.by_column(session, TagName=tag_name, TagType=tag_type)
        if tag is None:
            if tag_description is None:
                raise ValueError(
                    f"Tag '{tag_name}' does not exist and tag_description is required for new tags"
                )
            tag = Tag(
                TagName=tag_name,
                TagType=tag_type,
                TagDescription=tag_description,
                CreatorID=creator.CreatorID,
            )
            session.add(tag)
            session.flush()
        elif tag_description is not None and tag.TagDescription != tag_description:
            raise ValueError(
                f"Tag '{tag_name}' exists with different description: '{tag.TagDescription}' != '{tag_description}'"
            )

        # Get or create link
        link = SegmentationTagLink.by_pk(session, (tag.TagID, self.SegmentationID))
        if link is None:
            link = SegmentationTagLink(
                TagID=tag.TagID,
                SegmentationID=self.SegmentationID,
                CreatorID=creator.CreatorID,
                Comment=comment,
            )
            session.add(link)
            session.flush()
        elif comment is not None:
            link.Comment = comment
            session.flush()

        return link


class FeatureFeatureLink(Base):
    __tablename__ = "CompositeFeature"
    __table_args__ = (
        Index("fk_CompositeFeature_ParentFeature1_idx", "ParentFeatureID"),
        Index("fk_CompositeFeature_ChildFeature1_idx", "ChildFeatureID"),
    )

    ParentFeatureID: Mapped[int] = mapped_column(
        ForeignKey("Feature.FeatureID", ondelete="CASCADE"), primary_key=True
    )
    ChildFeatureID: Mapped[int] = mapped_column(
        ForeignKey("Feature.FeatureID", ondelete="RESTRICT"), primary_key=True
    )
    FeatureIndex: Mapped[int] = mapped_column(primary_key=True)

    Feature: Mapped["Feature"] = relationship(
        "eyened_orm.segmentation.Feature",
        back_populates="FeatureAssociations",
        foreign_keys="FeatureFeatureLink.ParentFeatureID",
    )

    Child: Mapped["Feature"] = relationship(
        "eyened_orm.segmentation.Feature",
        back_populates="ChildFeatureAssociations",
        foreign_keys="FeatureFeatureLink.ChildFeatureID",
    )


class Feature(Base):
    __tablename__ = "Feature"
    _name_column: ClassVar[str] = "FeatureName"

    FeatureID: Mapped[int] = mapped_column(primary_key=True)
    FeatureName: Mapped[str] = mapped_column(String(60), unique=True)

    Segmentations: Mapped[List["Segmentation"]] = relationship(
        "eyened_orm.segmentation.Segmentation", back_populates="Feature"
    )
    SegmentationModels: Mapped[List["SegmentationModel"]] = relationship(
        "eyened_orm.segmentation.SegmentationModel", back_populates="Feature"
    )
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships for parent-child feature hierarchy
    FeatureAssociations: Mapped[List["FeatureFeatureLink"]] = relationship(
        "eyened_orm.segmentation.FeatureFeatureLink",
        back_populates="Feature",
        foreign_keys="FeatureFeatureLink.ParentFeatureID",
        passive_deletes=True,
    )

    # Child side stays non-cascading (used only to detect blocking links)
    ChildFeatureAssociations: Mapped[List["FeatureFeatureLink"]] = relationship(
        "eyened_orm.segmentation.FeatureFeatureLink",
        back_populates="Child",
        foreign_keys="FeatureFeatureLink.ChildFeatureID",
    )

    @property
    def has_segmentations(self) -> bool:
        return bool(self.Segmentations)

    @property
    def is_child(self) -> bool:
        return bool(self.ChildFeatureAssociations)

    @classmethod
    def from_list(
        cls, session, feature_name: str, sub_features: List[str] | None = None
    ) -> "Feature":
        """
        Create a feature hierarchy from a list of feature names.
        If a feature does not exist, it will be created.
        If a feature already exists, it will be appended to the parent.
        """
        feature = cls(FeatureName=feature_name)
        session.add(feature)
        session.flush()

        if sub_features is None:
            return feature

        if isinstance(sub_features, list):
            # first create the sub-features that don't exist
            for sub_feature in sub_features:
                if Feature.by_name(session, sub_feature) is None:
                    session.add(Feature(FeatureName=sub_feature))
            session.flush()

            # then create the feature associations
            for i, sub_feature in enumerate(sub_features):
                feature.FeatureAssociations.append(
                    FeatureFeatureLink(
                        ParentFeatureID=feature.FeatureID,
                        ChildFeatureID=Feature.by_name(session, sub_feature).FeatureID,
                        FeatureIndex=i,
                    )
                )
        else:
            raise ValueError(f"Unsupported sub_features type: {type(sub_features)}")

        return feature

    @property
    def subfeatures(self) -> Dict[int, str]:
        assocs = sorted(self.FeatureAssociations, key=lambda x: x.FeatureIndex)
        return {assoc.FeatureIndex: assoc.Child.FeatureName for assoc in assocs}

    @property
    def json(self) -> Dict[str, Any]:
        assocs = sorted(self.FeatureAssociations, key=lambda x: x.FeatureIndex)
        subfeatures = [
            {"index": assoc.FeatureIndex, "name": assoc.Child.FeatureName}
            for assoc in assocs
        ]
        return {"FeatureName": self.FeatureName, "SubFeatures": subfeatures}


class Model(Base):
    __tablename__ = "Model"
    _name_column: ClassVar[str] = "ModelName"

    __table_args__ = (
        UniqueConstraint("ModelName", name="ModelName"),
        UniqueConstraint("ModelName", "Version"),
    )
    __mapper_args__ = {"polymorphic_on": "ModelType"}

    ModelID: Mapped[int] = mapped_column(primary_key=True)
    ModelName: Mapped[str] = mapped_column(String(255))
    Version: Mapped[str] = mapped_column(String(255))
    ModelType: Mapped[ModelKind] = mapped_column(
        SAEnum(
            ModelKind, name="modelkind", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
    )  # to distinguish between segmentation and attribute models
    # segmentation models have a feature and segmentations
    # attribute models have only attributes
    Description: Mapped[Optional[str]] = mapped_column(String(255))
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    # relationships
    ProducedAttributeValues: Mapped[List["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue", back_populates="ProducingModel"
    )


class SegmentationModel(Model):
    __tablename__ = "SegmentationModel"

    ModelID: Mapped[int] = mapped_column(
        ForeignKey("Model.ModelID", ondelete="CASCADE"), primary_key=True
    )
    FeatureID: Mapped[Optional[int]] = mapped_column(ForeignKey("Feature.FeatureID"))

    Feature: Mapped[Optional["Feature"]] = relationship(
        "eyened_orm.segmentation.Feature", back_populates="SegmentationModels"
    )
    Segmentations: Mapped[List["ModelSegmentation"]] = relationship(
        "eyened_orm.segmentation.ModelSegmentation", back_populates="Model"
    )

    __mapper_args__ = {"polymorphic_identity": ModelKind.Segmentation}


class ModelSegmentation(SegmentationBase):
    __tablename__ = "ModelSegmentation"
    __table_args__ = (
        Index("ix_ModelSegmentation_Model_Image", "ModelID", "ImageInstanceID"),
        Index("ix_ModelSegmentation_Image_Model", "ImageInstanceID", "ModelID"),
    )

    ModelSegmentationID: Mapped[int] = mapped_column(primary_key=True)
    ModelID: Mapped[int] = mapped_column(ForeignKey("Model.ModelID"))

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Model: Mapped["SegmentationModel"] = relationship(
        "eyened_orm.segmentation.SegmentationModel",
        back_populates="Segmentations",
        lazy="selectin",
    )
    ImageInstance: Mapped["ImageInstance"] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="ModelSegmentations"
    )
    AttributeValues: Mapped[List["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue",
        back_populates="ModelSegmentation",
        lazy="selectin",
    )

    @property
    def groupname(self) -> str:
        model = self.Model
        if model is not None:
            return f"model_{model.ModelName}_{model.Version}"
        # Fallback: query base Model directly by ID
        sess = object_session(self)
        if sess is not None:
            base_model = sess.get(Model, getattr(self, "ModelID", None))
            if base_model is not None:
                return f"model_{base_model.ModelName}_{base_model.Version}"
        return "model_name_unknown"

# Event Listeners
def validate_segmentation(mapper, connection, target):
    target.check_consistency()


def validate_immutable_dims(mapper, connection, target):
    # Check if history shows changes to dims
    from sqlalchemy.orm.attributes import get_history

    for attr in ["Depth", "Height", "Width"]:
        hist = get_history(target, attr)
        if hist.has_changes():
            raise ValueError(f"Cannot modify {attr} of a Segmentation once created.")
    target.check_consistency()


event.listen(Segmentation, "before_insert", validate_segmentation)
event.listen(Segmentation, "before_update", validate_immutable_dims)

event.listen(ModelSegmentation, "before_insert", validate_segmentation)
event.listen(ModelSegmentation, "before_update", validate_immutable_dims)
