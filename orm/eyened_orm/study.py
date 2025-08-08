from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, func, select, Index
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base, CompositeUniqueConstraint, ForeignKeyIndex
from .image_instance import DeviceInstance, ImageInstance

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, Patient, Series


class Study(Base):
    """
    Study class representing a visit (study) of a patient.
    All images taken on the same day are grouped into a study.
    """
    
    __tablename__ = "Study"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Patient", "PatientID"),
        # one study per patient per date
        CompositeUniqueConstraint("PatientID", "StudyDate"),
        # Add index on StudyDate for faster ordering and filtering
        Index('StudyDate_idx', 'StudyDate'),
    )

    StudyID: Mapped[int] = mapped_column(primary_key=True)
    PatientID: Mapped[int] = mapped_column(ForeignKey("Patient.PatientID"))
    StudyRound: Mapped[Optional[int]] = mapped_column(
        index=True
    ) 
    StudyDescription: Mapped[Optional[str]] = mapped_column(String(64))
    StudyInstanceUid: Mapped[Optional[str]] = mapped_column(
        "StudyInstanceUid", String(64), unique=True
    )
    StudyDate: Mapped[datetime.date] = mapped_column("StudyDate")

    # datetimes
    DateInserted: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    patient_date_to_id_map = None

    Patient: Patient = relationship("eyened_orm.patient.Patient", back_populates="Studies")
    Series: List[Series] = relationship(
        "eyened_orm.series.Series",
        back_populates="Study", cascade="all,delete-orphan"
    )
    Annotations: List[Annotation] = relationship("eyened_orm.annotation.Annotation", back_populates="Study")
    FormAnnotations: List[FormAnnotation] = relationship(
        "eyened_orm.form_annotation.FormAnnotation", back_populates="Study"
    )


    @classmethod
    def by_id(cls, session: Session, id: int):
        res = session.execute(select(Study).where(Study.StudyID == id)).first()
        if res is None:
            return None
        return res[0]

    @classmethod
    def by_uid(cls, session: Session, StudyInstanceUid: str):
        return session.scalar(
            select(Study).where(Study.StudyInstanceUid == StudyInstanceUid)
        )

    @classmethod
    def by_patient_and_date(
        cls, session: Session, patient_id, study_date
    ):
        return session.scalar(
            select(Study)
            .where(Study.PatientID == patient_id)
            .where(Study.StudyDate == study_date)
        )

    @property
    def age_years(self):
        if self.StudyDate is None or self.Patient.BirthDate is None:
            return None
        return (self.StudyDate - self.Patient.BirthDate).days / 365.25
    

    def get_images(self, where=None, include_inactive=False) -> List[ImageInstance]:
        from eyened_orm import Series, Study, Patient, DeviceInstance, DeviceModel
        session = Session.object_session(self)
        q = (
            select(ImageInstance)
            .join_from(ImageInstance, Series)
            .join_from(Series, Study)
            .join_from(Study, Patient)
            .join_from(ImageInstance, DeviceInstance)
            .join_from(DeviceInstance, DeviceModel)
            .where(Study.StudyID == self.StudyID)
        )
        if not include_inactive:
            q = q.where(~ImageInstance.Inactive)
        if where is not None:
            q = q.where(where)
        return session.scalars(q)

    def __repr__(self):
        return f"Study({self.StudyID}, {self.StudyDate}, {self.StudyInstanceUid}, {self.StudyDescription})"
