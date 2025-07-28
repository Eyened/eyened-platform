import enum
import string
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, List, Optional

import pandas as pd
from sqlalchemy import Column, Index, Text, select
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import Contact, Patient, Task


class ExternalEnum(int, enum.Enum):
    Y = 1
    N = 2
    M = 3


class ProjectBase(Base):

    ProjectName: str = Field(max_length=255, unique=True)
    External: ExternalEnum
    Description: str | None = Field(sa_column=Column(Text), default=None)
    ContactID: int | None = Field(foreign_key="Contact.ContactID")
    DOI: str | None = Field(max_length=255, default=None)


class Project(ProjectBase, table=True):

    __tablename__ = "Project"
    _name_column: ClassVar[str] = "ProjectName"
    ProjectID: int = Field(primary_key=True)
    DateInserted: datetime = Field(default_factory=datetime.now)

    Contact: Optional["Contact"] = Relationship(back_populates="Projects")

    Patients: List["Patient"] = Relationship(
        back_populates="Project", cascade_delete=True
    )

    def make_dataframe(self, session: Session) -> pd.DataFrame:
        """
        Returns a dataframe of all images in the project.
        """
        from eyened_orm import ImageInstance, Patient, Series, Study

        stmt = (
            select(ImageInstance, Series, Study, Patient)
            .select_from(ImageInstance)
            .join(Series)
            .join(Study)
            .join(Patient)
            .where(Patient.ProjectID == self.ProjectID)
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

    def get_patient_by_identifier(
        self, session: Session, patient_identifier: string
    ) -> Optional["Patient"]:
        """
        Returns a patient with the specified ID that belongs to this project.
        """
        from eyened_orm import Patient

        return session.scalar(
            select(Patient).where(
                Patient.PatientIdentifier == patient_identifier,
                Patient.ProjectID == self.ProjectID,
            )
        )

class ContactBase(Base):
    Name: str = Field(max_length=255)
    Email: str = Field(max_length=255)
    Institute: str | None = Field(max_length=255, default=None)
    Orcid: str | None = Field(max_length=255, default=None)

class Contact(ContactBase, table=True):
    __tablename__ = "Contact"
    __table_args__ = (
        Index("NameEmailInstitute_UNIQUE", "Name", "Email", "Institute", unique=True),
    )
    _name_column: ClassVar[str] = "Name"

    ContactID: int = Field(primary_key=True)
    
    Projects: List["Project"] = Relationship(back_populates="Contact")
    Tasks: List["Task"] = Relationship(back_populates="Contact")
