from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base, CompositeUniqueConstraint, ForeignKeyIndex
from .image_instance import ImageInstance
from .project import Project
from .series import Series
from .study import Study

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation


class SexEnum(int, enum.Enum):
    M = 1
    F = 2


class Patient(Base):
    __tablename__ = "Patient"
    __table_args__ = (
        # PatientIdentifier is UNIQUE per ProjectID
        CompositeUniqueConstraint("ProjectID", "PatientIdentifier"),
        ForeignKeyIndex(__tablename__, "Project", "ProjectID"),
    )

    PatientID: Mapped[int] = mapped_column(primary_key=True)
    BirthDate: Mapped[Optional[date]] = mapped_column()
    Sex: Mapped[Optional[SexEnum]] = mapped_column()
    PatientIdentifier: Mapped[Optional[str]] = mapped_column(String(45))

    ProjectID: Mapped[int] = mapped_column(ForeignKey("Project.ProjectID"))
    

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    # relationships
    Project = relationship("eyened_orm.project.Project", back_populates="Patients")

    Studies: List[Study] = relationship(
        "eyened_orm.study.Study", back_populates="Patient", cascade="all,delete-orphan"
    )
    Annotations: List[Annotation] = relationship(
        "eyened_orm.annotation.Annotation", back_populates="Patient")
    FormAnnotations: List[FormAnnotation] = relationship(
        "eyened_orm.form_annotation.FormAnnotation", back_populates="Patient"
    )

    @classmethod
    def by_project_and_identifier(
        cls, session, project_id: int, patient_identifier: str | int | None
    ) -> Patient:
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
    def by_identifier(cls, session, patient_identifier: str | int | None) -> List[Patient]:
        """
        Returns a list of patients with the given identifier 
        """
        return session.scalars(
            select(Patient).where(
                Patient.PatientIdentifier == patient_identifier
            )
        ).all()

    def get_study_by_date(self, study_date: date) -> Study:
        """
        Returns the study for this patient with the given study date.
        """
        return next(
            (study for study in self.Studies if study.StudyDate == study_date),
            None
        )

    def get_images(self, where=None, include_inactive=False) -> List[ImageInstance]:
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
        return session.scalars(q)

    def __repr__(self):
        return f"Patient({self.PatientID}, {self.PatientIdentifier}, {self.BirthDate}, {self.Sex})"
