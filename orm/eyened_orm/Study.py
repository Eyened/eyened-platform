from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base, CompositeUniqueConstraint, ForeignKeyIndex
from .ImageInstance import ImageInstance
from .Patient import Patient
from .Series import Series

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation


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
    )

    StudyID: Mapped[int] = mapped_column(primary_key=True)

    PatientID: Mapped[int] = mapped_column(ForeignKey("Patient.PatientID"))
    Patient: Mapped[Patient] = relationship(back_populates="Studies")

    Series: Mapped[List[Series]] = relationship(
        back_populates="Study", cascade="all,delete-orphan"
    )

    Annotations: Mapped[List[Annotation]] = relationship(back_populates="Study")
    FormAnnotations: Mapped[List["FormAnnotation"]] = relationship(
        back_populates="Study"
    )

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

    @classmethod
    def _make_patient_date_to_id_map(cls, session: Session):
        results = (
            session.execute(
                select(
                    Patient.PatientIdentifier, Study.StudyDate, Study.StudyID
                ).join_from(Study, Study.Patient)
            )
            .scalars()
            .all()
        )
        Study.patient_date_to_id_map = {(r[0], r[1]): r[2] for r in results}

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
    def from_patient_and_date(
        cls, session: Session, patient_identifier, study_date, preload=True
    ):
        if preload:
            if Study.patient_date_to_id_map is None:
                Study._make_patient_date_to_id_map(session)

            study_id = Study.patient_date_to_id_map.get(
                (patient_identifier, study_date), None
            )
            return Study.by_id(session, study_id)
        else:
            raise NotImplementedError()

    @property
    def age_years(self):
        if self.StudyDate is None or self.Patient.BirthDate is None:
            return None
        return (self.StudyDate - self.Patient.BirthDate).days / 365.25
    

    def get_images(self, where=None) -> List[ImageInstance]:
        session = Session.object_session(self)
        q = (
            select(ImageInstance)
            .where(~ImageInstance.Inactive)
            .join_from(ImageInstance, Series)
            .join_from(Series, Study)
            .where(Study.StudyID == self.StudyID)
        )
        if where is not None:
            q = q.where(where)
        return session.scalars(q)

    def __repr__(self):
        return f"Study({self.StudyID}, {self.StudyDate}, {self.StudyInstanceUid}, {self.StudyDescription})"
