import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, ClassVar, List, Optional

from sqlalchemy import select, Index
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship
from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (
        Annotation,
        FormAnnotation,
        Project,
        Series,
        Study,
        ImageInstance,
    )


class SexEnum(enum.Enum):
    M = 1
    F = 2

class PatientBase(Base):
    PatientIdentifier: str = Field(max_length=45)
    BirthDate: date | None
    Sex: SexEnum | None 
    ProjectID: int = Field(foreign_key="Project.ProjectID")

class Patient(PatientBase, table=True):
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

    PatientID: int = Field(primary_key=True)
    DateInserted: datetime = Field(default_factory=datetime.now)
    
    Project: "Project" = Relationship(back_populates="Patients")
    Studies: List["Study"] = Relationship(back_populates="Patient", cascade_delete=True)
    Annotations: List["Annotation"] = Relationship(back_populates="Patient")
    FormAnnotations: List["FormAnnotation"] = Relationship(back_populates="Patient")

    @classmethod
    def by_project_and_identifier(
        cls, session: Session, project_id: int, patient_identifier: str | int | None
    ) -> Optional["Patient"]:
        """
        Returns a patient with the given project ID and identifier.
        If no patient is found, raises an exception.
        """
        return session.scalar(
            select(Patient).where(
                Patient.ProjectID == project_id,
                Patient.PatientIdentifier == patient_identifier,
            )
        ).one()

    @classmethod
    def by_identifier(
        cls, session: Session, patient_identifier: str | int | None
    ) -> List["Patient"]:
        """
        Returns a list of patients with the given identifier
        """
        return cls.by_column(session, "PatientIdentifier", patient_identifier)

    def get_study_by_date(self, study_date: date) -> Optional["Study"]:
        """
        Returns the study for this patient with the given study date.
        """
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
