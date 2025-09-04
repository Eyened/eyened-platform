import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, ClassVar, List, Optional

from sqlalchemy import Index, String, ForeignKey, select, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (Annotation, FormAnnotation, ImageInstance, Project,
                            Study)


class SexEnum(enum.Enum):
    M = 1
    F = 2


class Patient(Base):
    __tablename__ = "Patient"
    __table_args__ = (
        Index(
            "ProjectIDPatientIdentifier_UNIQUE",
            "PatientIdentifier",
            "ProjectID",
            unique=True,
        ),
        Index("fk_Patient_Project1_idx", "ProjectID"),
    )

    _name_column: ClassVar[str] = "PatientIdentifier"

    PatientID: Mapped[int] = mapped_column(primary_key=True)
    PatientIdentifier: Mapped[str] = mapped_column(String(255))
    BirthDate: Mapped[Optional[date]]
    Sex: Mapped[Optional[SexEnum]] = mapped_column(SAEnum(SexEnum))
    ProjectID: Mapped[int] = mapped_column(ForeignKey("Project.ProjectID"))

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Project: Mapped["Project"] = relationship(back_populates="Patients")
    Studies: Mapped[List["Study"]] = relationship(back_populates="Patient", cascade="all, delete")
    Annotations: Mapped[List["Annotation"]] = relationship(back_populates="Patient")
    FormAnnotations: Mapped[List["FormAnnotation"]] = relationship(back_populates="Patient")

    @classmethod
    def by_project_and_identifier(
        cls, session: Session, project_id: int, patient_identifier: str | int | None
    ) -> Optional["Patient"]:
        """Return the patient with the given project ID and identifier."""
        from eyened_orm import Patient

        return session.scalar(
            select(Patient).where(
                Patient.ProjectID == project_id,
                Patient.PatientIdentifier == patient_identifier,
            )
        )

    @classmethod
    def by_identifier(
        cls, session: Session, patient_identifier: str | int | None
    ) -> List["Patient"]:
        """Return a list of patients with the given identifier."""
        return cls.by_columns(session, PatientIdentifier=patient_identifier)

    def get_study_by_date(self, study_date: date) -> Optional["Study"]:
        """Return the study for this patient with the given study date."""
        return next(
            (study for study in self.Studies if study.StudyDate == study_date), None
        )

    def get_images(self, where=None, include_inactive=False) -> List["ImageInstance"]:
        from eyened_orm import ImageInstance, Series, Study

        session = Session.object_session(self)
        q = (
            select(ImageInstance)
            .join(Series)
            .join(Study)
            .where(Study.PatientID == self.PatientID)
        )
        if not include_inactive:
            q = q.where(~ImageInstance.Inactive)
        if where is not None:
            q = q.where(where)
        return session.scalars(q).all()
