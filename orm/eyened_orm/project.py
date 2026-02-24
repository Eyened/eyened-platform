import enum
import string
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, List, Optional

import pandas as pd
from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Text,
    String,
    select,
    Enum as SAEnum,
    func,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import Contact, Patient, Task


class ExternalEnum(enum.Enum):
    Y = "Y"
    N = "N"
    M = "M"


class Project(Base):
    """Projects group patients and images; hold metadata and contact."""

    __tablename__ = "Project"

    _name_column: ClassVar[str] = "ProjectName"

    __table_args__ = (Index("fk_Project_Contact1_idx", "ContactID"),)

    ProjectID: Mapped[int] = mapped_column(primary_key=True)
    ProjectName: Mapped[str] = mapped_column(String(255), unique=True)
    External: Mapped[ExternalEnum] = mapped_column(SAEnum(ExternalEnum))
    Description: Mapped[Optional[str]] = mapped_column(Text)
    ContactID: Mapped[Optional[int]] = mapped_column(ForeignKey("Contact.ContactID"))
    DOI: Mapped[Optional[str]] = mapped_column(String(255))

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    Contact: Mapped[Optional["Contact"]] = relationship(
        "eyened_orm.project.Contact", back_populates="Projects"
    )

    Patients: Mapped[List["Patient"]] = relationship(
        "eyened_orm.patient.Patient", back_populates="Project", passive_deletes=True
    )

    def make_dataframe(self, session: Session) -> pd.DataFrame:
        """Return a dataframe of all images in the project."""
        from eyened_orm import ImageInstance, Patient, Series, Study

        image_ids = list(
            session.scalars(
                select(ImageInstance.ImageInstanceID)
                .select_from(ImageInstance)
                .join(Series)
                .join(Study)
                .join(Patient)
                .where(Patient.ProjectID == self.ProjectID)
            )
        )

        return ImageInstance.make_dataframe(session, image_ids)

    def get_images(
        self, include_inactive=False, where=None
    ) -> List["ImageInstance"]:
        from eyened_orm import ImageInstance, Series, Study, Patient

        session = Session.object_session(self)
        q = (
            select(ImageInstance)
            .join(Series)
            .join(Study)
            .join(Patient)
            .where(Patient.ProjectID == self.ProjectID)
        )
        if not include_inactive:
            q = q.where(~ImageInstance.Inactive)
        if where is not None:
            q = q.where(where)
        return session.scalars(q).all()

    def get_patient_by_identifier(
        self, session: Session, patient_identifier: string
    ) -> Optional["Patient"]:
        """Return a patient with the specified ID that belongs to this project."""
        from eyened_orm import Patient

        return session.scalar(
            select(Patient).where(
                Patient.PatientIdentifier == patient_identifier,
                Patient.ProjectID == self.ProjectID,
            )
        )

    def get_images(self, where=None, include_inactive=False) -> List["ImageInstance"]:
        from eyened_orm import ImageInstance, Series, Study, Patient

        session = Session.object_session(self)
        q = (
            select(ImageInstance)
            .join(Series)
            .join(Study)
            .join(Patient)
            .where(Patient.ProjectID == self.ProjectID)
        )
        if not include_inactive:
            q = q.where(~ImageInstance.Inactive)
        if where is not None:
            q = q.where(where)
        return session.scalars(q).all()



class Contact(Base):
    __tablename__ = "Contact"
    __table_args__ = (
        Index("NameEmailInstitute_UNIQUE", "Name", "Email", "Institute", unique=True),
    )
    _name_column: ClassVar[str] = "Name"

    ContactID: Mapped[int] = mapped_column(primary_key=True)
    Name: Mapped[str] = mapped_column(String(255))
    Email: Mapped[str] = mapped_column(String(255))
    Institute: Mapped[Optional[str]] = mapped_column(String(255))
    Orcid: Mapped[Optional[str]] = mapped_column(String(255))

    Projects: Mapped[List["Project"]] = relationship(
        "eyened_orm.project.Project", back_populates="Contact"
    )
    Tasks: Mapped[List["Task"]] = relationship(
        "eyened_orm.task.Task", back_populates="Contact"
    )
