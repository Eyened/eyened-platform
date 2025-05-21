import enum
import string
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

import pandas as pd 
from sqlalchemy import Column, Text, select, Index
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:   
    from eyened_orm import Patient, Task, Contact


class ExternalEnum(int, enum.Enum):
    Y = 1
    N = 2
    M = 3


class Project(Base, table=True):
    __tablename__ = "Project"
    ProjectID: int = Field(primary_key=True)
    ProjectName: str = Field(sa_column_kwargs={"unique": True}, max_length=45)
    External: ExternalEnum
    Description: str | None = Field(default=None, sa_column=Column(Text))

    ContactID: int | None = Field(default=None, foreign_key="Contact.ContactID")
    Contact: Optional["Contact"] = Relationship(back_populates="Projects")

    Patients: List["Patient"] = Relationship(
        back_populates="Project", cascade_delete=True
    )

    DateInserted: datetime = Field(default_factory=datetime.now)
    
    DOI: str | None = Field(default=None, max_length=256)


    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional["Project"]:
        return session.scalar(select(Project).where((Project.ProjectName == name)))

    def __repr__(self):
        return f"Project({self.ProjectID}, {self.ProjectName}, {self.External})"

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


class Contact(Base, table=True):
    __tablename__ = "Contact"
    __table_args__ = (
        Index("NameEmailInstitute_UNIQUE", "Name", "Email", "Institute", unique=True),
    )

    ContactID: int = Field(primary_key=True)
    Name: str = Field(max_length=256)
    Email: str = Field(max_length=256)
    Institute: str | None = Field(default=None, max_length=256)
    Orcid: str | None = Field(default=None, max_length=256)

    Projects: List["Project"] = Relationship(back_populates="Contact")
    Tasks: List["Task"] = Relationship(back_populates="Contact")
