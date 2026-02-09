from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Set
from eyened_orm.config import load_routing_settings
import numpy as np
import pandas as pd
import pydicom
from PIL import Image
from rtnls_fundusprep.cfi_bounds import CFIBounds
from rtnls_fundusprep.mask_extraction import get_cfi_bounds
import secrets
from sqlalchemy import ForeignKey, Index, String, event, func, select
from sqlalchemy.dialects.mysql import JSON, TEXT, TINYBLOB
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base
from .types import OptionalEnum

if TYPE_CHECKING:
    from eyened_orm import Annotation, Creator, ImageInstanceTagLink, Series

BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _make_public_id(length: int = 12) -> str:
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))


class Laterality(Enum):
    L = "L"
    R = "R"


class ModalityType(Enum):
    # thus far only encountered OP, OPT, SC
    # should perhaps be extended (https://dicom.nema.org/medical/Dicom/2024d/output/chtml/part16/chapter_D.html)
    # Ophthalmic Photography
    OP = "OP"
    # Ophthalmic Photography Tomography (used for OCT)
    OPT = "OPT"
    # Secondary Capture
    SC = "SC"


class Modality(Enum):
    # custom selection of commonly used ophthalmic modalities

    AdaptiveOptics = "AdaptiveOptics"
    ColorFundus = "ColorFundus"
    ColorFundusStereo = "ColorFundusStereo"
    RedFreeFundus = "RedFreeFundus"
    ExternalEye = "ExternalEye"
    LensPhotograph = "LensPhotograph"
    Ophthalmoscope = "Ophthalmoscope"

    Autofluorescence = "Autofluorescence"
    FluoresceinAngiography = "FluoresceinAngiography"
    ICGA = "ICGA"

    InfraredReflectance = "InfraredReflectance"
    BlueReflectance = "BlueReflectance"
    GreenReflectance = "GreenReflectance"

    OCT = "OCT"
    OCTA = "OCTA"


class ETDRSField(Enum):
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"


class StorageBackends(Base):
    __tablename__ = "storage_backends"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(256))
    config: Mapped[Any] = mapped_column(JSON)

    ImageInstances: Mapped[List["ImageInstance"]] = relationship(
        "eyened_orm.image_instance.ImageInstance",
        back_populates="storage_backend",
        lazy="noload",
    )


class ImageInstance(Base):
    __tablename__ = "ImageInstance"
    __table_args__ = (
        Index("fk_ImageInstance_Series_Inactive1_idx", "SeriesID", "Inactive"),
        Index("ix_ImageInstance_public_id", "public_id", unique=True),
        Index("fk_ImageInstance_DeviceInstance1_idx", "DeviceInstanceID"),
        Index("fk_ImageInstance_SourceInfo1_idx", "SourceInfoID"),
        Index("fk_ImageInstance_Modality1_idx", "ModalityID"),
        Index("fk_ImageInstance_Scan1_idx", "ScanID"),
        Index("fk_ImageInstance_Series1_idx", "SeriesID"),
        Index(
            "ix_ImageInstance_Modality_Inactive_Laterality",
            "Modality",
            "Inactive",
            "Laterality",
        ),
        Index(
            "ix_ImageInstance_Modality_Inactive_ETDRSField",
            "Modality",
            "Inactive",
            "ETDRSField",
        ),
        Index(
            "SOPInstanceUid_UNIQUE",
            "SOPInstanceUid",
            unique=True,
        ),
        Index(
            "SourceInfoIDDatasetIdentifier_UNIQUE",
            "DatasetIdentifier",
            "SourceInfoID",
            unique=True,
        ),
    )

    ImageInstanceID: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(12),
        unique=True,
        nullable=False,
    )

    storage_backend_id: Mapped[int] = mapped_column(
        ForeignKey("storage_backends.id"),
        nullable=False,
    )

    object_prefix: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
    )

    object_key: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    # repeating field, but non-nullable
    SeriesID: Mapped[int] = mapped_column(
        ForeignKey("Series.SeriesID", ondelete="CASCADE")
    )
    SourceInfoID: Mapped[int] = mapped_column(ForeignKey("SourceInfo.SourceInfoID"))
    DeviceInstanceID: Mapped[int] = mapped_column(
        ForeignKey("DeviceInstance.DeviceInstanceID")
    )
    # TODO: redundant with Modality enum
    ModalityID: Mapped[Optional[int]] = mapped_column(ForeignKey("Modality.ModalityID"))
    ScanID: Mapped[Optional[int]] = mapped_column(ForeignKey("Scan.ScanID"))

    # Image modality
    Modality: Mapped[Optional[Modality]] = mapped_column(OptionalEnum(Modality))

    # DICOM metadata
    SOPInstanceUid: Mapped[Optional[str]] = mapped_column(String(64))
    SOPClassUid: Mapped[Optional[str]] = mapped_column(String(64))
    PhotometricInterpretation: Mapped[Optional[str]] = mapped_column(String(64))
    SamplesPerPixel: Mapped[Optional[int]]

    # image dimensions
    # Note on image orientation conventions:
    #
    # The physical direction of Rows and Columns can differ between imaging modalities:
    #
    # CFI and other fundus imaging modalities (typically):
    #     - Rows: height in the fundus (superior <-> inferior)
    #     - Columns: width in the fundus (lateral <-> temporal)
    #     - NrOfFrames: 1 for single-frame images
    # OCT, for a raster/volume with horizontal B-scans:
    #     - Rows: height of the B-scan (vitreous <-> choroid)
    #     - Columns: width of the B-scan (lateral <-> temporal)
    #     - NrOfFrames: number of B-scans (superior <-> inferior for horizontal B-scan)

    Rows_y: Mapped[Optional[int]]  # Height of the image (in pixels)
    Columns_x: Mapped[Optional[int]]  # Width of the image (in pixels)
    NrOfFrames: Mapped[Optional[int]]  # Used to for number of B-scans in OCT

    # resolution (all in millimeters)
    SliceThickness: Mapped[
        Optional[float]
    ]  # Nominal slice thickness for raster OCT scans
    ResolutionAxial: Mapped[
        Optional[float]
    ]  # OCT-depth resolution (vitreous <-> choroid)
    ResolutionHorizontal: Mapped[
        Optional[float]
    ]  # Enface resolution (lateral <-> temporal)
    ResolutionVertical: Mapped[
        Optional[float]
    ]  # Enface resolution (superior <-> inferior)

    HorizontalFieldOfView: Mapped[Optional[float]]  # in degrees

    Laterality: Mapped[Optional[Laterality]] = mapped_column(
        OptionalEnum(Laterality)
    )  # L or R
    DICOMModality: Mapped[Optional[ModalityType]] = mapped_column(
        OptionalEnum(ModalityType)
    )  # OP, OPT, SC
    AnatomicRegion: Mapped[
        Optional[int]
    ]  # TODO: check (1 = OD, 2 = Macula, check ETDRSField?)
    ETDRSField: Mapped[Optional[ETDRSField]] = mapped_column(
        OptionalEnum(ETDRSField)
    )  # F1-F7
    Angiography: Mapped[Optional[int]]  # 0 = non-angiography, 1 = angiography

    AcquisitionDateTime: Mapped[
        Optional[datetime]
    ]  # Date and time the acquisition of data started
    PupilDilated: Mapped[Optional[bool]]

    # Relative filepath to the image file
    DatasetIdentifier: Mapped[str] = mapped_column(String(256))
    # Alternative relative filepath to the image file. Typically a lower resolution version of the image.
    AltDatasetIdentifier: Mapped[Optional[str]] = mapped_column(String(256))

    # identifier for the thumbnail (project_id/thumbnail_name), needs suffix for different sizes
    ThumbnailPath: Mapped[Optional[str]] = mapped_column(String(256))

    # Used to link to IDs of the image in the source database
    OldPath: Mapped[Optional[str]] = mapped_column(String(256))
    FDAIdentifier: Mapped[Optional[int]]

    # Considered removed from the database
    Inactive: Mapped[bool] = mapped_column(default=False)

    # Fundus-specific columns
    CFROI: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    CFKeypoints: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    CFQuality: Mapped[Optional[float]]

    # File checksum and data hash
    FileChecksum: Mapped[Optional[bytes]] = mapped_column(TINYBLOB)
    DataHash: Mapped[Optional[bytes]] = mapped_column(TINYBLOB)

    # relationships:
    Series: Mapped["Series"] = relationship(
        "eyened_orm.series.Series", back_populates="ImageInstances", lazy="selectin"
    )
    storage_backend: Mapped["StorageBackends"] = relationship(
        "eyened_orm.image_instance.StorageBackends",
        back_populates="ImageInstances",
        lazy="selectin",
    )
    SourceInfo: Mapped["SourceInfo"] = relationship(
        "eyened_orm.image_instance.SourceInfo",
        back_populates="ImageInstances",
        lazy="selectin",
    )
    DeviceInstance: Mapped["DeviceInstance"] = relationship(
        "eyened_orm.image_instance.DeviceInstance",
        back_populates="ImageInstances",
        lazy="selectin",
    )
    _Modality: Mapped[Optional["ModalityTable"]] = relationship(
        "eyened_orm.image_instance.ModalityTable", back_populates="ImageInstances"
    )
    Scan: Mapped[Optional["Scan"]] = relationship(
        "eyened_orm.image_instance.Scan",
        back_populates="ImageInstances",
        lazy="selectin",
    )

    # Datetimes - automatically filled
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())
    DateModified: Mapped[Optional[datetime]] = mapped_column(onupdate=func.now())
    # DatePreprocessed is the date and time the image was last preprocessed
    DatePreprocessed: Mapped[Optional[datetime]]

    # relationships:
    Annotations: Mapped[List["Annotation"]] = relationship(
        "eyened_orm.annotation.Annotation",
        back_populates="ImageInstance",
        passive_deletes=True,
    )

    Segmentations: Mapped[List["Segmentation"]] = relationship(
        "eyened_orm.segmentation.Segmentation",
        back_populates="ImageInstance",
        passive_deletes=True,
    )

    ModelSegmentations: Mapped[List["ModelSegmentation"]] = relationship(
        "eyened_orm.segmentation.ModelSegmentation",
        back_populates="ImageInstance",
        passive_deletes=True,
    )

    FormAnnotations: Mapped[List["FormAnnotation"]] = relationship(
        "eyened_orm.form_annotation.FormAnnotation",
        back_populates="ImageInstance",
        passive_deletes=True,
    )

    SubTaskImageLinks: Mapped[List["SubTaskImageLink"]] = relationship(
        "eyened_orm.task.SubTaskImageLink",
        back_populates="ImageInstance",
        passive_deletes=True,
    )

    ImageInstanceTagLinks: Mapped[Set["ImageInstanceTagLink"]] = relationship(
        "eyened_orm.tag.ImageInstanceTagLink",
        back_populates="ImageInstance",
        lazy="selectin",
    )

    # attributes relationship
    AttributeValues: Mapped[List["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue",
        back_populates="ImageInstance",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def shape(self) -> tuple[int, int, int]:
        return (self.NrOfFrames or 1, self.Rows_y, self.Columns_x)

    @property
    def is_3d(self) -> bool:
        return self.NrOfFrames is not None and self.NrOfFrames > 1

    @property
    def is_2d(self) -> bool:
        return not self.is_3d

    @property
    def Study(self):
        return self.Series.Study

    @property
    def date(self):
        return self.Study.StudyDate

    @property
    def Patient(self):
        return self.Study.Patient

    @property
    def PatientIdentifier(self):
        return self.Patient.PatientIdentifier

    @property
    def path(self) -> Path:
        routing_settings = load_routing_settings()
        try:
            root = routing_settings[self.storage_backend.key]
        except KeyError:
            raise ValueError(
                f"Storage backend key {self.storage_backend.key} not found in routing settings"
            )
        return Path(root) / (self.object_prefix or "") / self.object_key

    def get_thumbnail_path(self, size: int) -> str:
        routing_settings = load_routing_settings()
        try:
            root = routing_settings['thumbnails']
        except KeyError:
            raise ValueError(
                "Thumbnails routing settings not found"
            )
        return f"{root}/{self.ThumbnailPath}_{size}.jpg"

    @property
    def device_str(self):
        model = self.DeviceInstance.DeviceModel
        return f"{model.Manufacturer} {model.ManufacturerModelName}"

    @property
    def pixel_array(self):
        """Return the raw data for this image as a numpy array"""
        if self.DatasetIdentifier.endswith(".dcm"):
            ds = pydicom.dcmread(self.path)
            return ds.pixel_array
        elif self.DatasetIdentifier.endswith(".binary"):
            with open(self.path, "rb") as f:
                raw = np.frombuffer(f.read(), dtype=np.uint8)
                data = raw.reshape((-1, self.Rows_y, self.Columns_x), order="C")
            return data
        elif self.DatasetIdentifier.startswith("[png_series_"):
            prefix, filename = self.DatasetIdentifier.split("]", 1)
            n_files = int(prefix[len("[png_series_") :])
            base_path = self.config.images_basepath / filename
            return np.array(
                [
                    np.array(Image.open(base_path.parent / f"{base_path.stem}_{i}.png"))
                    for i in range(n_files)
                ]
            ).squeeze()
        else:
            return np.array(Image.open(self.path))

    @property
    def bounds(self) -> CFIBounds:
        pixel_array = self.pixel_array
        shape = pixel_array.shape
        if len(shape) == 3 and shape[2] > 4:
            raise ValueError("Can only handle 2D images")
        if self.CFROI is not None:
            # use bounds from database
            return CFIBounds(**self.CFROI, image=pixel_array)

        bounds = get_cfi_bounds(pixel_array)
        return bounds

    def make_cropped_image(self, diameter: int = 1024) -> np.ndarray:
        if self.bounds is None:
            return None
        M, bounds = self.bounds.crop(diameter)
        return M.warp(self.pixel_array, (diameter, diameter))

    @property
    def cropping_matrix(self) -> Optional[np.ndarray]:
        """3x3 transformation matrix from original image to 1024x1024 square space"""
        if self.bounds is None:
            return None
        return self.bounds.get_cropping_transform(1024).M

    @property
    def cropping_matrix_inverse(self) -> Optional[np.ndarray]:
        """3x3 transformation matrix from 1024x1024 square to original image space"""
        if self.bounds is None:
            return None
        return self.bounds.get_cropping_transform(1024).M_inv

    def calc_data_hash(self):
        """Return the hash of the image data"""
        import hashlib

        if not self.path.exists():
            raise FileNotFoundError(f"File {self.path} does not exist")

        # Get the raw data as numpy array
        data = self.pixel_array

        # Ensure the array is contiguous in memory for consistent byte representation
        contiguous_data = np.ascontiguousarray(data)

        # Convert to bytes and calculate hash
        data_bytes = contiguous_data.tobytes()
        return hashlib.sha256(data_bytes).hexdigest()

    def calc_file_checksum(self):
        """Return the checksum of the file"""
        import hashlib

        if not self.path.exists():
            raise FileNotFoundError(f"File {self.path} does not exist")

        md5_hash = hashlib.md5()

        with open(self.path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.digest()

    @classmethod
    def _base_joins(cls, statement):
        """Add useful joins for ImageInstance queries."""
        from eyened_orm import Patient, Project, Series, Study

        return (
            statement.join(Series)
            .join(Study)
            .join(Patient)
            .join(Project)
            .outerjoin(Scan)
            .outerjoin(DeviceInstance)
            .outerjoin(DeviceModel)
        )

    def get_annotations_for_creator(self, creator: "Creator") -> List["Annotation"]:
        """
        Get all annotations for this image instance for a specific creator
        :param creator_id: ID of the creator
        :return: list of annotations
        """
        return [a for a in self.Annotations if a.CreatorID == creator.CreatorID]

    @classmethod
    def make_dataframe(cls, session: Session, image_ids: List[int]) -> pd.DataFrame:
        """Make a dataframe of image instances"""
        images = cls.by_ids(session, image_ids)
        return pd.DataFrame([im.to_dict() for im in images.values()])

    def make_tag(
        self,
        tag_name: str,
        creator_name: str,
        comment: Optional[str] = None,
        tag_description: Optional[str] = None,
    ) -> "ImageInstanceTagLink":
        """Create or reuse a tag and link it to this image instance."""
        from eyened_orm import Creator, Tag, TagType
        from eyened_orm.tag import ImageInstanceTagLink

        session = self.session
        tag_type = TagType.ImageInstance

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
        link = ImageInstanceTagLink.by_pk(session, (tag.TagID, self.ImageInstanceID))
        if link is None:
            link = ImageInstanceTagLink(
                TagID=tag.TagID,
                ImageInstanceID=self.ImageInstanceID,
                CreatorID=creator.CreatorID,
                Comment=comment,
            )
            session.add(link)
            session.flush()
        elif comment is not None:
            link.Comment = comment
            session.flush()

        return link


@event.listens_for(ImageInstance, "before_insert")
def _image_instance_set_public_id(mapper, connection, target) -> None:
    if not target.public_id:
        target.public_id = _make_public_id()


class DeviceModel(Base):
    __tablename__ = "DeviceModel"
    __table_args__ = (
        Index(
            "ManufacturerManufacturerModelName_UNIQUE",
            "Manufacturer",
            "ManufacturerModelName",
            unique=True,
        ),
    )
    _name_column: ClassVar[str] = "ManufacturerModelName"

    DeviceModelID: Mapped[int] = mapped_column(primary_key=True)
    Manufacturer: Mapped[str] = mapped_column(String(45))
    ManufacturerModelName: Mapped[str] = mapped_column(String(45))

    DeviceInstances: Mapped[List["DeviceInstance"]] = relationship(
        "eyened_orm.image_instance.DeviceInstance", back_populates="DeviceModel"
    )

    @classmethod
    def by_manufacturer(
        cls, Manufacturer: str, ManufacturerModelName: str, session: Session
    ) -> Optional["DeviceModel"]:
        return session.scalar(
            select(cls).where(
                DeviceModel.Manufacturer == Manufacturer,
                DeviceModel.ManufacturerModelName == ManufacturerModelName,
            )
        )


class DeviceInstance(Base):
    __tablename__ = "DeviceInstance"
    __table_args__ = (
        Index(
            "DeviceModelIDDescription_UNIQUE",
            "DeviceModelID",
            "Description",
            unique=True,
        ),
    )

    DeviceInstanceID: Mapped[int] = mapped_column(primary_key=True)
    DeviceModelID: Mapped[int] = mapped_column(ForeignKey("DeviceModel.DeviceModelID"))
    SerialNumber: Mapped[Optional[str]] = mapped_column(TEXT)
    Description: Mapped[str] = mapped_column(String(256))

    DeviceModel: Mapped["DeviceModel"] = relationship(
        "eyened_orm.image_instance.DeviceModel", back_populates="DeviceInstances"
    )

    ImageInstances: Mapped[List[ImageInstance]] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="DeviceInstance"
    )


class SourceInfo(Base):
    __tablename__ = "SourceInfo"
    _name_column: ClassVar[str] = "SourceName"

    SourceInfoID: Mapped[int] = mapped_column(primary_key=True)
    SourceName: Mapped[str] = mapped_column(String(64), unique=True)

    SourcePath: Mapped[str] = mapped_column(String(250), unique=True)
    ThumbnailPath: Mapped[str] = mapped_column(String(250), unique=True)

    ImageInstances: Mapped[List["ImageInstance"]] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="SourceInfo"
    )


class ModalityTable(Base):
    __tablename__ = "Modality"
    _name_column: ClassVar[str] = "ModalityTag"

    ModalityID: Mapped[int] = mapped_column(primary_key=True)
    ModalityTag: Mapped[str] = mapped_column(String(40), unique=True)

    ImageInstances: Mapped[List["ImageInstance"]] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="_Modality"
    )

    @classmethod
    def by_tag(cls, ModalityTag: str, session: Session) -> Optional["ModalityTable"]:
        return cls.by_column(session, ModalityTag=ModalityTag)


class Scan(Base):
    __tablename__ = "Scan"
    _name_column: ClassVar[str] = "ScanMode"

    ScanID: Mapped[int] = mapped_column(primary_key=True)
    ScanMode: Mapped[str] = mapped_column(String(40), unique=True)

    ImageInstances: Mapped[List["ImageInstance"]] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="Scan"
    )

    @classmethod
    def by_mode(cls, ScanMode: str, session: Session) -> Optional["Scan"]:
        return cls.by_column(session, ScanMode=ScanMode)
