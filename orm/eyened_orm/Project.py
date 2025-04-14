from __future__ import annotations

import enum
import string
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

import pandas as pd
from sqlalchemy import ForeignKey, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base, CompositeUniqueConstraintMulti

if TYPE_CHECKING:
    from eyened_orm import Patient, Task


class ExternalEnum(int, enum.Enum):
    Y = 1
    N = 2
    M = 3


class Project(Base):
    __tablename__ = "Project"
    ProjectID: Mapped[int] = mapped_column(primary_key=True)
    ProjectName: Mapped[str] = mapped_column(String(45), unique=True)
    External: Mapped[ExternalEnum] = mapped_column()
    Description: Mapped[Optional[str]] = mapped_column(Text)

    ContactID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Contact.ContactID"))
    Contact: Mapped[Optional[Contact]] = relationship(
        back_populates="Projects")

    Patients: Mapped[List[Patient]] = relationship(
        back_populates="Project", cascade="all,delete-orphan"
    )

    # datetimes
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    @classmethod
    def by_name(cls, session: Session, name: str) -> Project:
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

    def get_patient_by_identifier(self, patient_identifier: string, session: Session) -> Optional[Patient]:
        """
        Returns a patient with the specified ID that belongs to this project.
        """
        return session.scalar(
            select(Patient).where(
                (Patient.PatientIdentifier == patient_identifier) &
                (Patient.ProjectID == self.ProjectID)
            )
        )


class Contact(Base):
    __tablename__ = "Contact"
    __table_args__ = (CompositeUniqueConstraintMulti(
        ("Name", "Email", "Institute")),)

    ContactID: Mapped[int] = mapped_column(primary_key=True)
    Name = mapped_column(String(256), unique=False, nullable=False)
    Email = mapped_column(String(256), unique=False, nullable=False)
    Institute = mapped_column(String(256), unique=False)
    Projects: Mapped[List[Project]] = relationship(back_populates="Contact")
    Tasks: Mapped[List[Task]] = relationship(back_populates="Contact")
