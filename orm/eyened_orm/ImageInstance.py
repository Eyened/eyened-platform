# Note: this can cause issues
# https://github.com/fastapi/sqlmodel/discussions/900
# from future import annotations
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional


import numpy as np
import pandas as pd
import pydicom
from PIL import Image
from sqlalchemy import Column, Index, select
from sqlalchemy.dialects.mysql import JSON, TEXT, TINYBLOB
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import Annotation, Creator, Series


class Laterality(Enum):
    L = 1
    R = 2


class ModalityType(Enum):
    # thus far only encountered OP, OPT, SC
    # should perhaps be extended (https://dicom.nema.org/medical/Dicom/2024d/output/chtml/part16/chapter_D.html)
    # Ophthalmic Photography
    OP = 1
    # Ophthalmic Photography Tomography (used for OCT)
    OPT = 2
    # Secondary Capture
    SC = 3


class Modality(Enum):
    # custom selection of commonly used ophthalmic modalities

    AdaptiveOptics = 1
    ColorFundus = 2
    ColorFundusStereo = 3
    RedFreeFundus = 4
    ExternalEye = 5
    LensPhotograph = 6
    Ophthalmoscope = 7

    Autofluorescence = 8
    FluoresceinAngiography = 9
    ICGA = 10

    InfraredReflectance = 11
    BlueReflectance = 12
    GreenReflectance = 13

    OCT = 14
    OCTA = 15


class ETDRSField(Enum):
    F1 = 1
    F2 = 2
    F3 = 3
    F4 = 4
    F5 = 5
    F6 = 6
    F7 = 7

class AxisEnum(Enum):
    WIDTH = 0
    HEIGHT = 1
    DEPTH = 2


class ImageInstanceBase(Base):
    SeriesID: int | None = Field(foreign_key="Series.SeriesID", ondelete="CASCADE", default=None)
    SourceInfoID: int | None = Field(foreign_key="SourceInfo.SourceInfoID", default=None)
    DeviceInstanceID: int | None = Field(foreign_key="DeviceInstance.DeviceInstanceID", default=None)
    # TODO: redundant with Modality enum
    ModalityID: int | None = Field(foreign_key="Modality.ModalityID", default=None)
    ScanID: int | None = Field(foreign_key="Scan.ScanID", default=None)

    # Image modality
    Modality: Optional[Modality]
    
    # DICOM metadata
    SOPInstanceUid: str | None = Field(max_length=64, default=None)
    SOPClassUid: str | None = Field(max_length=64, default=None)
    PhotometricInterpretation: str | None = Field(max_length=64, default=None)
    SamplesPerPixel: int | None

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
    
    Rows_y: int | None  # Height of the image (in pixels)
    Columns_x: int | None  # Width of the image (in pixels)
    NrOfFrames: int | None  # Used to for number of B-scans in OCT

    # resolution (all in millimeters)
    SliceThickness: float | None  # Nominal slice thickness for raster OCT scans
    ResolutionAxial: float | None  # OCT-depth resolution (vitreous <-> choroid)
    ResolutionHorizontal: float | None  # Enface resolution (lateral <-> temporal)
    ResolutionVertical: float | None  # Enface resolution (superior <-> inferior)

    HorizontalFieldOfView: float | None  # in degrees

    Laterality: Optional[Laterality]  # L or R
    DICOMModality: Optional[ModalityType]  # OP, OPT, SC
    AnatomicRegion: int | None  # TODO: check (1 = OD, 2 = Macula, check ETDRSField?)
    ETDRSField: Optional[ETDRSField]  # F1-F7
    Angiography: int | None  # 0 = non-angiography, 1 = angiography

    AcquisitionDateTime: (
        datetime | None
    )  # Date and time the acquisition of data started
    PupilDilated: bool | None

    # Relative filepath to the image file
    DatasetIdentifier: str = Field(max_length=256)

    # identifier for the thumbnail (project_id/thumbnail_name), needs suffix for different sizes
    ThumbnailPath: str | None = Field(max_length=256)

    # Used to link to IDs of the image in the source database
    OldPath: str | None = Field(max_length=256)
    FDAIdentifier: int | None

    # Considered removed from the database
    Inactive: bool = False

    # Fundus-specific columns
    # CFROI contains the fundus bounds, eg.
    # {
    #     "lines": {},
    #     "max_x": 2048,
    #     "max_y": 1536,
    #     "min_x": 0,
    #     "min_y": 0,
    #     "center": [1021.7938260323712, 751.6328910976617],
    #     "radius": 688.1397816206166,
    # }
    # Can be read by CFIBounds from rtnls_fundusprep

    CFROI: Optional[Dict[str, Any]] = Field(sa_column=Column(JSON))
    # CFKeypoints holds fundus keypoint data
    # {
    #     "fovea_xy": [525.3117339804495, 781.470218347899],
    #     "disc_edge_xy": [1038.7284831576292, 778.7821723259435],
    #     "prep_fovea_xy": [142.60000610351562, 534.2000122070312],
    #     "prep_disc_edge_xy": [524.5999755859375, 532.2000122070312]
    # }
    # keys prefixed with prep are keypoint locations in the preprocessed image
    CFKeypoints: Optional[Dict[str, Any]] = Field(sa_column=Column(JSON))
    # Model assessment of fundus quality
    CFQuality: float | None

    # File checksum and data hash
    # FileChecksum is an MD5 hash of the file.
    # stored in case we want to someday implement file integrity checks
    # not meant to be used for duplicate checks
    FileChecksum: bytes | None = Field(sa_column=Column(TINYBLOB))
    # DataHash is the hash of the raw, uncompressed and decoded image information
    # used to prevent the insertion of duplicate images
    # and detect duplicates even when the metadata might be different
    DataHash: bytes | None = Field(sa_column=Column(TINYBLOB))


class ImageInstance(ImageInstanceBase, table=True):
    __tablename__ = "ImageInstance"
    __table_args__ = (
        Index("fk_ImageInstance_Series1_idx", "SeriesID"),
        Index("fk_ImageInstance_DeviceInstance1_idx", "DeviceInstanceID"),
        Index("fk_ImageInstance_SourceInfo1_idx", "SourceInfoID"),
        Index("fk_ImageInstance_Modality1_idx", "ModalityID"),
        Index("fk_ImageInstance_Scan1_idx", "ScanID"),
        Index("SOPInstanceUid_UNIQUE", "SOPInstanceUid", unique=True),
        Index(
            "SourceInfoIDDatasetIdentifier_UNIQUE",
            "DatasetIdentifier",
            "SourceInfoID",
            unique=True,
        ),
    )
    ImageInstanceID: int | None = Field(default=None, primary_key=True)

    # repeating field, but non-nullable
    SeriesID: int = Field(foreign_key="Series.SeriesID", ondelete="CASCADE")
    SourceInfoID: int = Field(foreign_key="SourceInfo.SourceInfoID")
    DeviceInstanceID: int = Field(foreign_key="DeviceInstance.DeviceInstanceID")
    # TODO: redundant with Modality enum
    ModalityID: int = Field(foreign_key="Modality.ModalityID")
    
    # relationships:
    Series: "Series" = Relationship(back_populates="ImageInstances")
    SourceInfo: "SourceInfo" = Relationship(back_populates="ImageInstances")
    DeviceInstance: "DeviceInstance" = Relationship(back_populates="ImageInstances")
    _Modality: "ModalityTable" = Relationship(back_populates="ImageInstances")
    Scan: Optional["Scan"] = Relationship(back_populates="ImageInstances")

    # Datetimes - automatically filled
    DateInserted: datetime = Field(default_factory=datetime.now)
    DateModified: datetime | None = Field(
        default_factory=datetime.now, sa_column_kwargs={"onupdate": datetime.now}
    )
    # DatePreprocessed is the date and time the image was last preprocessed
    DatePreprocessed: datetime | None

    # relationships:
    Annotations: List["Annotation"] = Relationship(
        back_populates="ImageInstance", cascade_delete=True
    )

    Segmentations: List["Segmentation"] = Relationship(
        back_populates="ImageInstance", cascade_delete=True
    )

    FormAnnotations: List["FormAnnotation"] = Relationship(
        back_populates="ImageInstance", cascade_delete=True
    )

    SubTaskImageLinks: List["SubTaskImageLink"] = Relationship(
        back_populates="ImageInstance"
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
    def Patient(self):
        return self.Study.Patient

    @property
    def PatientIdentifier(self):
        return self.Patient.PatientIdentifier

    @property
    def path(self) -> Path:
        return Path(self.config.images_basepath) / self.DatasetIdentifier

    def get_thumbnail_path(self, size: int) -> Path:
        return Path(self.config.thumbnails_path) / f"{self.ThumbnailPath}_{size}.jpg"

    @property
    def url(self):
        if self.config.image_server_url is None:
            raise RuntimeError("image_server_url not set in config")
        return f"{self.config.image_server_url}/{self.DatasetIdentifier}"

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
            base_path = Path(self.config.images_basepath) / filename
            return np.array(
                [
                    np.array(Image.open(base_path.parent / f"{base_path.stem}_{i}.png"))
                    for i in range(n_files)
                ]
            ).squeeze()
        else:
            return np.array(Image.open(self.path))

    @property
    def bounds(self):
        pixel_array = self.pixel_array
        shape = pixel_array.shape
        if len(shape) == 3 and shape[2] > 4:
            raise ValueError("Can only handle 2D images")
        if self.CFROI is not None:
            # use bounds from database
            from rtnls_fundusprep.cfi_bounds import CFIBounds

            return CFIBounds(**self.CFROI, image=pixel_array)

        from rtnls_fundusprep.mask_extraction import get_cfi_bounds

        bounds = get_cfi_bounds(pixel_array)
        self.CFROI = bounds.to_dict_all()
        return bounds

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
    def where(cls, clause, include_inactive=False):
        """
        return a query with some useful joins
        usage example:

            q = ImageInstance.where(DeviceModel.ManufacturerModelName == 'HRA')
            session.scalar(q.limit(1))
        """
        from eyened_orm import Patient, Project, Series, Study

        statement = select(ImageInstance)
        if not include_inactive:
            statement = statement.where(~ImageInstance.Inactive)
        return (
            statement.join(Series)
            .join(Study)
            .join(Patient)
            .join(Project)
            .outerjoin(Scan)
            .outerjoin(DeviceInstance)
            .outerjoin(DeviceModel)
            .where(clause)
        )

    def get_annotations_for_creator(self, creator: "Creator") -> List["Annotation"]:
        """
        Get all annotations for this image instance for a specific creator
        :param creator_id: ID of the creator
        :return: list of annotations
        """
        return [a for a in self.Annotations if a.CreatorID == creator.CreatorID]

class DeviceModelBase(Base):
    Manufacturer: str = Field(max_length=45)
    ManufacturerModelName: str = Field(max_length=45)

class DeviceModel(DeviceModelBase, table=True):
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

    DeviceModelID: int = Field(primary_key=True)

    DeviceInstances: List["DeviceInstance"] = Relationship(back_populates="DeviceModel")

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


class DeviceInstanceBase(Base):
    DeviceModelID: int = Field(foreign_key="DeviceModel.DeviceModelID")
    SerialNumber: str | None = Field(sa_column=Column(TEXT))
    Description: str = Field(max_length=256)


class DeviceInstance(DeviceInstanceBase, table=True):
    __tablename__ = "DeviceInstance"
    __table_args__ = (
        Index(
            "DeviceModelIDDescription_UNIQUE",
            "DeviceModelID",
            "Description",
            unique=True,
        ),
    )

    DeviceInstanceID: int = Field(primary_key=True)
    DeviceModel: "DeviceModel" = Relationship(back_populates="DeviceInstances")

    ImageInstances: List["ImageInstance"] = Relationship(
        back_populates="DeviceInstance"
    )


class SourceInfo(Base, table=True):
    __tablename__ = "SourceInfo"
    _name_column: ClassVar[str] = "SourceName"

    SourceInfoID: int = Field(primary_key=True)
    SourceName: str = Field(max_length=64, unique=True)

    SourcePath: str = Field(max_length=250, unique=True)
    ThumbnailPath: str = Field(max_length=250, unique=True)

    ImageInstances: List["ImageInstance"] = Relationship(back_populates="SourceInfo")


class ModalityTable(Base, table=True):
    __tablename__ = "Modality"
    _name_column: ClassVar[str] = "ModalityTag"

    ModalityID: int = Field(primary_key=True)
    ModalityTag: str = Field(max_length=40, unique=True)

    ImageInstances: List["ImageInstance"] = Relationship(back_populates="_Modality")

    @classmethod
    def by_tag(cls, ModalityTag: str, session: Session) -> Optional["ModalityTable"]:
        return cls.by_column(session, ModalityTag=ModalityTag)


class ScanBase(Base):
    ScanMode: str = Field(max_length=40, unique=True)

class Scan(ScanBase, table=True):
    __tablename__ = "Scan"
    _name_column: ClassVar[str] = "ScanMode"

    ScanID: int = Field(primary_key=True)
    
    ImageInstances: List["ImageInstance"] = Relationship(back_populates="Scan")

    @classmethod
    def by_mode(cls, ScanMode: str, session: Session) -> Optional["Scan"]:
        return cls.by_column(session, ScanMode=ScanMode)


