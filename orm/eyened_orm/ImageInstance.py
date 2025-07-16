from __future__ import annotations

import enum
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional


import numpy as np
import pandas as pd
import pydicom
from PIL import Image
from sqlalchemy import ForeignKey, LargeBinary, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base, CompositeUniqueConstraint, ForeignKeyIndex

if TYPE_CHECKING:
    from eyened_orm import (Annotation, Creator, FormAnnotation, Series,
                            SubTaskImageLink)


class Laterality(enum.Enum):
    L = 1
    R = 2


class ModalityType(enum.Enum):
    # thus far only encountered OP, OPT, SC
    # should perhaps be extended (https://dicom.nema.org/medical/Dicom/2024d/output/chtml/part16/chapter_D.html)
    # Ophthalmic Photography
    OP = 1
    # Ophthalmic Photography Tomography (used for OCT)
    OPT = 2
    # Secondary Capture
    SC = 3


class Modality(enum.Enum):
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


class ETDRSField(enum.Enum):
    F1 = 1
    F2 = 2
    F3 = 3
    F4 = 4
    F5 = 5
    F6 = 6
    F7 = 7


class ImageInstance(Base):
    __tablename__ = "ImageInstance"
    __table_args__ = (
        CompositeUniqueConstraint("SourceInfoID", "DatasetIdentifier"),
        ForeignKeyIndex(__tablename__, "Series", "SeriesID"),
        ForeignKeyIndex(__tablename__, "DeviceInstance", "DeviceInstanceID"),
        ForeignKeyIndex(__tablename__, "SourceInfo", "SourceInfoID"),
        ForeignKeyIndex(__tablename__, "Modality", "ModalityID"),
        ForeignKeyIndex(__tablename__, "Scan", "ScanID"),
    )
    ImageInstanceID: Mapped[int] = mapped_column(primary_key=True)

    SeriesID: Mapped[int] = mapped_column(
        ForeignKey("Series.SeriesID", ondelete="CASCADE")
    )
    Series: Mapped[Series] = relationship(back_populates="ImageInstances")

    # TODO: not needed anymore?
    SourceInfoID: Mapped[int] = mapped_column(
        ForeignKey("SourceInfo.SourceInfoID"))
    SourceInfo: Mapped[SourceInfo] = relationship(
        back_populates="ImageInstances")

    DeviceInstanceID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("DeviceInstance.DeviceInstanceID")
    )
    DeviceInstance: Mapped[DeviceInstance] = relationship(
        back_populates="ImageInstances"
    )

    # TODO: redundant with Modality enum
    ModalityID: Mapped[int] = mapped_column(ForeignKey("Modality.ModalityID"))
    _Modality: Mapped[ModalityTable] = relationship(
        back_populates="ImageInstances")

    ScanID: Mapped[Optional[int]] = mapped_column(ForeignKey("Scan.ScanID"))
    Scan: Mapped[Scan] = relationship(back_populates="ImageInstances")

    # Image modality
    Modality: Mapped[Optional[Modality]]

    # DICOM metadata
    SOPInstanceUid: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True)  # Unique identifier for SOP instance (image)
    SOPClassUid: Mapped[Optional[str]] = mapped_column(
        String(64))  # Identifies the service-object pair class
    # Specifies the intended interpretation of pixel data (RGB, MONOCHROME, etc.)
    PhotometricInterpretation: Mapped[Optional[str]] = mapped_column(
        String(64))
    # Number of color components in each pixel
    SamplesPerPixel: Mapped[Optional[int]]
    # Number of frames in a multi-frame image
    NrOfFrames: Mapped[Optional[int]]
    # Nominal slice thickness, in millimeters
    SliceThickness: Mapped[Optional[float]]
    Rows_y: Mapped[Optional[int]]  # Number of rows (height) in the image
    Columns_x: Mapped[Optional[int]]  # Number of columns (width) in the image
    # Side of body examined (left or right)
    Laterality: Mapped[Optional[Laterality]]
    # Type of equipment that acquired the data (OP = Ophthalmic Photography)
    DICOMModality: Mapped[Optional[ModalityType]]
    AnatomicRegion: Mapped[Optional[int]]  # Body part examined
    # Early Treatment Diabetic Retinopathy Study field position (not standard DICOM)
    ETDRSField: Mapped[Optional[ETDRSField]]
    # Indicates angiography type (not standard DICOM)
    Angiography: Mapped[Optional[int]]
    # Date and time the acquisition of data started
    AcquisitionDateTime: Mapped[Optional[datetime]]
    # Indicates if pupil was dilated during image acquisition (ophthalmic-specific)
    PupilDilated: Mapped[Optional[bool]]
    # Horizontal dimension of field of view in millimeters
    HorizontalFieldOfView: Mapped[Optional[float]]
    # Axial resolution in millimeters (not standard DICOM)
    ResolutionAxial: Mapped[Optional[float]]
    # Horizontal resolution in millimeters (not standard DICOM)
    ResolutionHorizontal: Mapped[Optional[float]]
    # Vertical resolution in millimeters (not standard DICOM)
    ResolutionVertical: Mapped[Optional[float]]

    # Relative filepath to the image file
    DatasetIdentifier: Mapped[str] = mapped_column(String(256), index=True)

    # Relative filepath to the thumbnail file
    ThumbnailIdentifier: Mapped[Optional[str]] = mapped_column(String(256))
    ThumbnailPath: Mapped[Optional[str]] = mapped_column(String(256))

    # Original IDs of the image in the source database
    OldPath: Mapped[Optional[str]] = mapped_column(String(256))
    FDAIdentifier: Mapped[Optional[int]]

    # Considered removed from the database
    Inactive: Mapped[bool] = mapped_column(server_default="0")

    # Fundus-specific columns
    # CFROI contains the fundus bounds, eg.
    # {
    # "lines": {},
    # "max_x": 2048,
    # "max_y": 1536,
    # "min_x": 0,
    # "min_y": 0,
    # "center": [1021.7938260323712, 751.6328910976617],
    # "radius": 688.1397816206166,
    # }
    # Can be read by CFIBounds from rtnls_fundusprep
    # from rtnls_fundusprep.cfi_bounds import CFIBounds
    # bounds = copy.deepcopy(image_instance.CFROI)
    # bounds["hw"] = (image_instance.Rows_y, image_instance.Columns_x)
    # cfroi = CFIBounds(**bounds)
    CFROI: Mapped[Optional[Dict[str, Any]]]
    # CFKeypoints holds fundus keypoint data
    # {
    # "fovea_xy": [525.3117339804495, 781.470218347899],
    # "disc_edge_xy": [1038.7284831576292, 778.7821723259435],
    # "prep_fovea_xy": [142.60000610351562, 534.2000122070312],
    # "prep_disc_edge_xy": [524.5999755859375, 532.2000122070312]
    # }
    # keys prefixed with prep are keypoint locations in the preprocessed image
    CFKeypoints: Mapped[Optional[Dict[str, Any]]]
    # Model assessment of fundus quality
    CFQuality: Mapped[Optional[float]]

    # File checksum and data hash
    # FileChecksum is an MD5 hash of the file.
    # stored in case we want to someday implement file integrity checks
    # not meant to be used for duplicate checks
    FileChecksum: Mapped[Optional[bytes]] = mapped_column(LargeBinary(16))
    # DataHash is the hash of the raw, uncompressed and decoded image information
    # used to prevent the insertion of duplicate images
    # and detect duplicates even when the metadata might be different
    DataHash: Mapped[Optional[bytes]] = mapped_column(LargeBinary(32))

    # Datetimes - automatically filled
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())
    DateModified: Mapped[Optional[datetime]] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    # DatePreprocessed is the date and time the image was last preprocessed
    DatePreprocessed: Mapped[Optional[datetime]]

    # relationships:
    Annotations: Mapped[List[Annotation]] = relationship(
        back_populates="ImageInstance", cascade="all,delete-orphan"
    )

    FormAnnotations: Mapped[List[FormAnnotation]] = relationship(
        back_populates="ImageInstance", cascade="all,delete-orphan"
    )

    SubTaskImageLinks: Mapped[List[SubTaskImageLink]] = relationship(
        back_populates="ImageInstance"
    )

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
        '''
        The local path to the image on the server. 
        When running in Docker, this path is within the container (ie. /images/...)
        and may not exist on the host machine.
        '''
        return Path(self.config.images_basepath) / self.DatasetIdentifier
    
    @property
    def host_path(self) -> Path:
        '''
        The path to the image on the host machine.
        If images_basepath_host is not set in config, raise an error.
        '''
        if self.config.images_basepath_host is None:
            raise RuntimeError("images_basepath_host not set in config")
        return Path(self.config.images_basepath_host) / self.DatasetIdentifier
    
    @property
    def thumbnail_path(self) -> Path:
        '''
        The path to the thumbnail on the server.
        When running in Docker, this path is within the container (ie. /thumbnails/...)
        and may not exist on the host machine.
        '''
        if self.ThumbnailIdentifier is None:
            raise RuntimeError("ThumbnailIdentifier not set in config")
        return Path(self.config.thumbnails_path) / self.ThumbnailIdentifier

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
                data = raw.reshape(
                    (-1, self.Rows_y, self.Columns_x), order="C")
            return data
        else:
            return np.array(Image.open(self.path))

    def calc_data_hash(self):
        """Return the hash of the image data"""
        import hashlib

        import numpy as np

        if not os.path.exists(self.path):
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

        if not os.path.exists(self.path):
            raise FileNotFoundError(f"File {self.path} does not exist")

        md5_hash = hashlib.md5()

        with open(self.path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.digest()

    @classmethod
    def where(cls, clause):
        """
        return a query with some useful joins
        usage example: 

            q = ImageInstance.where(DeviceModel.ManufacturerModelName == 'HRA')
            session.scalar(q.limit(1))
        """
        from eyened_orm import Patient, Project, Series, Study

        return (
            select(ImageInstance)
            .where(~ImageInstance.Inactive)
            .join(Series).join(Study).join(Patient).join(Project)
            .outerjoin(Scan)
            .outerjoin(DeviceInstance)
            .outerjoin(DeviceModel)
            .where(clause)
        )

    def get_annotations_for_creator(self, creator: Creator) -> List[Annotation]:
        """
        Get all annotations for this image instance for a specific creator
        :param creator_id: ID of the creator
        :return: list of annotations
        """
        return [a for a in self.Annotations
                if a.CreatorID == creator.CreatorID]
    
    @classmethod
    def make_dataframe(cls, session: Session, image_ids: list[int]) -> pd.DataFrame:
        """
        Make a dataframe from a list of ImageInstance objects
        """
        from eyened_orm import Patient, Series, Study

        stmt = (
            select(ImageInstance, Series, Study, Patient)
            .select_from(ImageInstance)
            .join(Series)
            .join(Study)
            .join(Patient)
            .where(ImageInstance.ImageInstanceID.in_(image_ids))
        )

        rows = session.execute(stmt).all()

        # Convert rows to a DataFrame
        df = pd.DataFrame(
            [
                {
                    "image_id": im.ImageInstanceID,
                    "patient_id": pat.PatientID,
                    "patient_identifier": pat.PatientIdentifier,
                    "study_id": study.StudyID,
                    "study_date": study.StudyDate,
                    "series_id": series.SeriesID,
                    "path": im.path,
                }
                for im, series, study, pat in rows
            ]
        )
        return df

    def __repr__(self):
        return f"ID: {self.ImageInstanceID} @ {self.SourceInfo.SourcePath} {self.DatasetIdentifier}"


class DeviceModel(Base):
    __tablename__ = "DeviceModel"
    __table_args__ = (
        CompositeUniqueConstraint("Manufacturer", "ManufacturerModelName"),
    )
    DeviceModelID: Mapped[int] = mapped_column(primary_key=True)

    Manufacturer: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=False)
    ManufacturerModelName: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=False
    )

    DeviceInstances: Mapped[List["DeviceInstance"]] = relationship(
        back_populates="DeviceModel"
    )

    def __init__(self, Manufacturer="", ManufacturerModelName=""):
        self.Manufacturer = Manufacturer
        self.ManufacturerModelName = ManufacturerModelName

    def __repr__(self):
        return f"{self.DeviceModelID} - {self.Manufacturer} {self.ManufacturerModelName}"

    @classmethod
    def by_manufacturer(cls, Manufacturer: str, ManufacturerModelName: str, session: Session
                        ) -> DeviceModel:
        return session.scalar(
            select(cls)
            .where(
                DeviceModel.Manufacturer == Manufacturer,
                DeviceModel.ManufacturerModelName == ManufacturerModelName
            )
        )


class DeviceInstance(Base):
    __tablename__ = "DeviceInstance"
    __table_args__ = (CompositeUniqueConstraint(
        "DeviceModelID", "Description"),)

    DeviceInstanceID: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True)
    DeviceModelID: Mapped[int] = mapped_column(
        ForeignKey("DeviceModel.DeviceModelID"), nullable=False
    )
    SerialNumber: Mapped[str] = mapped_column(Text, nullable=True)
    Description: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=False)

    ImageInstances: Mapped[List["ImageInstance"]] = relationship(
        back_populates="DeviceInstance"
    )
    DeviceModel: Mapped["DeviceModel"] = relationship(
        back_populates="DeviceInstances")

    def __init__(
        self, DeviceModelID: int, SerialNumber: str, Description: Optional[str] = None
    ):
        self.DeviceModelID = DeviceModelID
        self.SerialNumber = SerialNumber
        self.Description = Description


class SourceInfo(Base):
    __tablename__ = "SourceInfo"
    SourceInfoID: Mapped[int] = mapped_column(primary_key=True)
    SourceName: Mapped[str] = mapped_column(String(64), unique=True)

    SourcePath: Mapped[str] = mapped_column(String(250), unique=True)
    ThumbnailPath: Mapped[str] = mapped_column(String(250), unique=True)

    ImageInstances: Mapped[List[ImageInstance]] = relationship(
        back_populates="SourceInfo"
    )

    def __repr__(self) -> str:
        return f"{self.SourceName}: {self.SourcePath}"

    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional[SourceInfo]:
        return session.scalar(select(cls).where(cls.SourceName == name))


class ModalityTable(Base):
    __tablename__ = "Modality"
    ModalityID: Mapped[int] = mapped_column(primary_key=True)
    ModalityTag: Mapped[str] = mapped_column(String(40), unique=True)

    # one modality -> many images
    ImageInstances: Mapped[List[ImageInstance]] = relationship(
        back_populates="_Modality"
    )

    @classmethod
    def by_tag(cls, ModalityTag: str, session: Session) -> Optional[ModalityTable]:
        return session.scalar(
            select(cls).where(cls.ModalityTag == ModalityTag)
        )


class Scan(Base):
    __tablename__ = "Scan"
    ScanID: Mapped[int] = mapped_column(primary_key=True)
    ScanMode: Mapped[str] = mapped_column(String(40), unique=True)

    ImageInstances: Mapped[List[ImageInstance]
                           ] = relationship(back_populates="Scan")

    @classmethod
    def by_mode(cls, ScanMode: str, session: Session) -> Scan:
        return session.scalar(
            select(cls).where(cls.ScanMode == ScanMode)
        )
