import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import select, Index
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship
from .base import Base

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, Project, Series, Study


class SexEnum(int, enum.Enum):
    M = 1
    F = 2


class Patient(Base, table=True):
    __tablename__ = "Patient"
    __table_args__ = (
        Index("ProjectIDPatientIdentifier_UNIQUE", "PatientIdentifier", "ProjectID", unique=True),
        Index("fk_Patient_Project1_idx", "ProjectID"),
    )

    PatientID: int = Field(primary_key=True)
    BirthDate: date | None = None
    Sex: SexEnum | None = None
    PatientIdentifier: str | None = Field(max_length=45)

    ProjectID: int = Field(foreign_key="Project.ProjectID")
    Project: "Project" = Relationship(back_populates="Patients")

    Studies: List["Study"] = Relationship(back_populates="Patient", cascade_delete=True)

    DateInserted: datetime = Field(default_factory=datetime.now)

    # relationships
    Annotations: List['Annotation'] = Relationship(back_populates="Patient")
    FormAnnotations: List['FormAnnotation'] = Relationship(back_populates="Patient")

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
                Patient.PatientIdentifier == patient_identifier
            )
        ).one()

    @classmethod
    def by_identifier(cls, session: Session, patient_identifier: str | int | None) -> List["Patient"]:
        """
        Returns a list of patients with the given identifier 
        """
        return session.scalars(
            select(Patient).where(
                Patient.PatientIdentifier == patient_identifier
            )
        ).all()

    def get_study_by_date(self, study_date: date) -> Optional["Study"]:
        """
        Returns the study for this patient with the given study date.
        """
        return next(
            (study for study in self.Studies if study.StudyDate == study_date),
            None
        )

    def get_images(self, where=None, include_inactive=False) -> List["ImageInstance"]:
        session = Session.object_session(self)
        q = (
            select(ImageInstance)
            .join_from(ImageInstance, Series)
            .join_from(Series, Study)
            .join_from(Study, Patient)
            .where(Patient.PatientID == self.PatientID)
        )
        if not include_inactive:
            q = q.where(~ImageInstance.Inactive)
        if where is not None:
            q = q.where(where)
        return session.scalars(q).all()

    def __repr__(self):
        return f"Patient({self.PatientID}, {self.PatientIdentifier}, {self.BirthDate}, {self.Sex})"
