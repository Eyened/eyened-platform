import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import select, Index
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship

from .base import Base


if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, Patient, Series, ImageInstance


class Study(Base, table=True):
    """
    Study class representing a visit (study) of a patient.
    All images taken on the same day are grouped into a study.
    """

    __tablename__ = "Study"
    __table_args__ = (
        Index("PatientIDStudyDate_UNIQUE", "StudyDate", "PatientID", unique=True),
        Index("fk_Study_Patient1_idx", "PatientID"),
        Index("StudyDate_idx", "StudyDate"),
        Index("StudyRound", "StudyRound"),
    )

    StudyID: int = Field(primary_key=True)

    PatientID: int = Field(foreign_key="Patient.PatientID")
    Patient: "Patient" = Relationship(back_populates="Studies")

    Series: List["Series"] = Relationship(back_populates="Study")
    Annotations: List["Annotation"] = Relationship(back_populates="Study")
    FormAnnotations: List["FormAnnotation"] = Relationship(back_populates="Study")

    StudyRound: int | None = Field()
    StudyDescription: str | None = Field(max_length=64)

    StudyInstanceUid: str | None = Field(max_length=64, unique=True)
    StudyDate: datetime.date

    # datetimes
    DateInserted: datetime.datetime = Field(default_factory=datetime.datetime.now)

    @classmethod
    def by_uid(cls, session: Session, StudyInstanceUid: str) -> Optional["Study"]:
        return cls.by_column(session, "StudyInstanceUid", StudyInstanceUid)

    @classmethod
    def by_patient_and_date(
        cls, session: Session, patient_id: int, study_date: datetime.date
    ) -> Optional["Study"]:
        return session.scalar(
            select(Study).where(
                Study.PatientID == patient_id, Study.StudyDate == study_date
            )
        )

    @property
    def age_years(self) -> float | None:
        if self.StudyDate is None or self.Patient.BirthDate is None:
            return None
        return (self.StudyDate - self.Patient.BirthDate).days / 365.25

    def get_images(self, where=None, include_inactive=False) -> List["ImageInstance"]:
        session = Session.object_session(self)
        q = select(ImageInstance).join(Series).where(Series.StudyID == self.StudyID)
        if not include_inactive:
            q = q.where(~ImageInstance.Inactive)
        if where is not None:
            q = q.where(where)
        return session.scalars(q).all()

class Series(Base, table=True):
    __tablename__ = "Series"
    __table_args__ = (Index("fk_Series_Study1_idx", "StudyID"),)

    SeriesID: int = Field(primary_key=True)

    StudyID: int = Field(foreign_key="Study.StudyID", ondelete="CASCADE")
    Study: "Study" = Relationship(back_populates="Series")

    SeriesNumber: int | None
    SeriesInstanceUid: str | None = Field(max_length=64, unique=True)

    ImageInstances: List["ImageInstance"] = Relationship(back_populates="Series")
    Annotations: List["Annotation"] = Relationship(back_populates="Series")

    def get_images(self, where=None, include_inactive=False) -> List["ImageInstance"]:
        session = Session.object_session(self)
        q = select(ImageInstance).where(ImageInstance.SeriesID == self.SeriesID)
        if not include_inactive:
            q = q.where(~ImageInstance.Inactive)
        if where is not None:
            q = q.where(where)
        return session.scalars(q).all()
