from __future__ import annotations

import enum
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
import pydicom
from PIL import Image
from sqlalchemy import ForeignKey, LargeBinary, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base, CompositeUniqueConstraint, ForeignKeyIndex

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, Series, SubTaskImageLink


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
    SourceInfoID: Mapped[int] = mapped_column(ForeignKey("SourceInfo.SourceInfoID"))
    SourceInfo: Mapped[SourceInfo] = relationship(back_populates="ImageInstances")

    DeviceInstanceID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("DeviceInstance.DeviceInstanceID")
    )
    DeviceInstance: Mapped[DeviceInstance] = relationship(
        back_populates="ImageInstances"
    )

    # TODO: redundant with Modality enum
    ModalityID: Mapped[int] = mapped_column(ForeignKey("Modality.ModalityID"))
    _Modality: Mapped[ModalityTable] = relationship(back_populates="ImageInstances")

    ScanID: Mapped[Optional[int]] = mapped_column(ForeignKey("Scan.ScanID"))
    Scan: Mapped[Scan] = relationship(back_populates="ImageInstances")

    Modality: Mapped[Optional[Modality]]

    SOPInstanceUid: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    SOPClassUid: Mapped[Optional[str]] = mapped_column(String(64))

    # MONOCHROME OR RGB (perhaps make enum?)
    PhotometricInterpretation: Mapped[Optional[str]] = mapped_column(String(64))
    
    SamplesPerPixel: Mapped[Optional[int]]
    
    # TODO: rename
    Rows_y: Mapped[Optional[int]]
    Columns_x: Mapped[Optional[int]]
    NrOfFrames: Mapped[Optional[int]]

    # TODO: there is something wrong here, using 4 resolution values for 3 dimensions    
    SliceThickness: Mapped[Optional[float]]
    ResolutionAxial: Mapped[Optional[float]]
    ResolutionHorizontal: Mapped[Optional[float]]
    ResolutionVertical: Mapped[Optional[float]]

    Laterality: Mapped[Optional[Laterality]]
    DICOMModality: Mapped[Optional[ModalityType]]

    
    # https://www.researchgate.net/figure/ETDRS-fields-definition-Courtesy-of-ETDRS-Research-Group-6_fig1_4072011
    # TODO: AnatomicRegion is the same as ETDRS Field ?
    AnatomicRegion: Mapped[Optional[int]]    
    ETDRSField: Mapped[Optional[ETDRSField]]
    
    
    Angiography: Mapped[Optional[int]]
    AcquisitionDateTime: Mapped[Optional[datetime]]
    PupilDilated: Mapped[Optional[bool]]
    HorizontalFieldOfView: Mapped[Optional[float]]

    # filename
    DatasetIdentifier: Mapped[str] = mapped_column(String(256), index=True)
    ThumbnailIdentifier: Mapped[Optional[str]] = mapped_column(String(256))
    ThumbnailPath: Mapped[Optional[str]] = mapped_column(String(256))
    
    OldPath: Mapped[Optional[str]] = mapped_column(String(256))
    # used for topcon images
    FDAIdentifier: Mapped[Optional[int]]

    # This default is not picked up by Alembic
    Inactive: Mapped[bool] = mapped_column(server_default="0")

    # Fundus-specific columns
    # TODO: merge?
    CFROI: Mapped[Optional[Dict[str, Any]]]
    CFKeypoints: Mapped[Optional[Dict[str, Any]]]
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

    # datetimes
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())
    DateModified: Mapped[Optional[datetime]] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
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
    def path(self):
        if "images_basepath" not in self.config:
            raise RuntimeError("images_basepath not set in config")
        return os.path.join(self.config["images_basepath"], self.DatasetIdentifier)

    @property
    def url(self):
        if "image_server_url" not in self.config:
            raise RuntimeError("image_server_url not set in config")
        return f"{self.config['image_server_url']}/{self.DatasetIdentifier}"

    @property
    def raw_data(self):
        """Return the raw data for this image as a numpy array"""
        if self.DatasetIdentifier.endswith(".dcm"):
            ds = pydicom.read_file(self.path)
            return ds.pixel_array
        elif self.DatasetIdentifier.endswith(".binary"):
            with open(self.path, "rb") as f:
                raw = np.frombuffer(f.read(), dtype=np.uint8)
                data = raw.reshape((-1, self.Rows_y, self.Columns_x), order="C")
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
        data = self.raw_data

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

    def __repr__(self):
        return f"ID: {self.ImageInstanceID} @ {self.SourceInfo.SourcePath} {self.DatasetIdentifier}"


class DeviceModel(Base):
    __tablename__ = "DeviceModel"
    __table_args__ = (
        CompositeUniqueConstraint("Manufacturer", "ManufacturerModelName"),
    )
    DeviceModelID: Mapped[int] = mapped_column(primary_key=True)
    
    Manufacturer: Mapped[Optional[str]] = mapped_column(String(45), nullable=False)
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
        return f"{self.DeviceID} - {self.Manufacturer} {self.ManufacturerModelName}"


    @classmethod
    def by_manufacturer(cls, Manufacturer: str, ManufacturerModelName: str, session:Session
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
    __table_args__ = (CompositeUniqueConstraint("DeviceModelID", "Description"),)

    DeviceInstanceID: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    DeviceModelID: Mapped[int] = mapped_column(
        ForeignKey("DeviceModel.DeviceModelID"), nullable=False
    )
    SerialNumber: Mapped[str] = mapped_column(Text, nullable=True)
    Description: Mapped[Optional[str]] = mapped_column(String(256), nullable=False)

    ImageInstances: Mapped[List["ImageInstance"]] = relationship(
        back_populates="DeviceInstance"
    )
    DeviceModel: Mapped["DeviceModel"] = relationship(back_populates="DeviceInstances")

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
    def by_tag(cls, ModalityTag: str, session:Session) -> Optional[ModalityTable]:
        return session.scalar(
            select(cls).where(cls.ModalityTag == ModalityTag)
        )
        


class Scan(Base):
    __tablename__ = "Scan"
    ScanID: Mapped[int] = mapped_column(primary_key=True)
    ScanMode: Mapped[str] = mapped_column(String(40), unique=True)

    ImageInstances: Mapped[List[ImageInstance]] = relationship(back_populates="Scan")

    @classmethod
    def by_mode(cls, ScanMode: str, session:Session) -> Scan:
        return session.scalar(
            select(cls).where(cls.ScanMode == ScanMode)
        )
