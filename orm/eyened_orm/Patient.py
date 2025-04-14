from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CompositeUniqueConstraint, ForeignKeyIndex

if TYPE_CHECKING:
    from eyened_orm import Annotation, FormAnnotation, Study, Project


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
    Project: Mapped[Project] = relationship(back_populates="Patients")

    Studies: Mapped[List[Study]] = relationship(
        back_populates="Patient", cascade="all,delete-orphan"
    )

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    # relationships
    Annotations: Mapped[List[Annotation]] = relationship(
        back_populates="Patient")
    FormAnnotations: Mapped[List[FormAnnotation]] = relationship(
        back_populates="Patient"
    )

    @classmethod
    def by_identifier(cls, session, identifier: str | int) -> Patient:
        return session.scalar(
            select(Patient).where(Patient.PatientIdentifier == identifier)
        )

    def get_study_by_date(self, study_date: date) -> Study:
        """
        Returns the study for this patient with the given study date.
        """
        return next(
            study for study in self.Studies if study.StudyDate == study_date
        )

    def __repr__(self):
        return f"Patient({self.PatientID}, {self.PatientIdentifier}, {self.BirthDate}, {self.Sex})"
