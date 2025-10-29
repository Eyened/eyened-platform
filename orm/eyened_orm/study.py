import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import select, Index, String, ForeignKey, func
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base


if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, Patient, Series as SeriesType, ImageInstance, StudyTagLink


class Study(Base):
    """A visit (study) of a patient; groups images taken on the same day."""

    __tablename__ = "Study"
    __table_args__ = (
        Index("PatientIDStudyDate_UNIQUE", "StudyDate", "PatientID", unique=True),
        Index("fk_Study_Patient1_idx", "PatientID"),
        Index("StudyDate_idx", "StudyDate"),
        Index("StudyRound", "StudyRound"),
    )

    StudyID: Mapped[int] = mapped_column(primary_key=True)
    PatientID: Mapped[int] = mapped_column(ForeignKey("Patient.PatientID", ondelete="CASCADE"))
    StudyRound: Mapped[Optional[int]]
    StudyDescription: Mapped[Optional[str]] = mapped_column(String(64))
    StudyInstanceUid: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    StudyDate: Mapped[datetime.date]

    DateInserted: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    Patient: Mapped["Patient"] = relationship("eyened_orm.patient.Patient", back_populates="Studies", lazy="selectin")
    Series: Mapped[List["Series"]] = relationship("eyened_orm.series.Series", back_populates="Study", passive_deletes=True)
    Annotations: Mapped[List["Annotation"]] = relationship("eyened_orm.annotation.Annotation", back_populates="Study")
    FormAnnotations: Mapped[List["FormAnnotation"]] = relationship("eyened_orm.form_annotation.FormAnnotation", back_populates="Study")

    StudyTagLinks: Mapped[List["StudyTagLink"]] = relationship("eyened_orm.tag.StudyTagLink", back_populates="Study", lazy="selectin")

    @classmethod
    def by_uid(cls, session: Session, StudyInstanceUid: str) -> Optional["Study"]:
        return cls.by_column(session, StudyInstanceUid=StudyInstanceUid)

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
        from eyened_orm import ImageInstance, Series
        q = select(ImageInstance).join(Series).where(Series.StudyID == self.StudyID)
        if not include_inactive:
            q = q.where(~ImageInstance.Inactive)
        if where is not None:
            q = q.where(where)
        session = Session.object_session(self)
        return session.scalars(q).all()
