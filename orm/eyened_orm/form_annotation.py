from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pandas import DataFrame, json_normalize
from sqlalchemy import ForeignKey, String, func, select, event
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship
import json

from .base import Base

if TYPE_CHECKING:
    from .annotation import Creator
    from .form_annotation import FormAnnotation
    from .image_instance import ImageInstance
    from .patient import Patient
    from .study import Study
    from .task import SubTask


class FormSchema(Base):
    __tablename__ = "FormSchema"

    FormSchemaID: Mapped[int] = mapped_column(primary_key=True)
    SchemaName: Mapped[Optional[str]] = mapped_column(String(45), unique=True)
    Schema: Mapped[Optional[Dict[str, Any]]]

    FormAnnotations: Mapped[List[FormAnnotation]] = relationship(
        "eyened_orm.form_annotation.FormAnnotation", back_populates="FormSchema"
    )

    def __repr__(self):
        return f"FormSchema({self.FormSchemaID}, {self.SchemaName})"

    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional[FormSchema]:
        """Find a FormSchema by name (SchemaName)."""
        return session.scalar(select(cls).where(cls.SchemaName == name))


class FormAnnotation(Base):
    __tablename__ = "FormAnnotation"

    FormAnnotationID: Mapped[int] = mapped_column(primary_key=True)

    FormSchemaID: Mapped[int] = mapped_column(
        ForeignKey("FormSchema.FormSchemaID"), index=True
    )
    FormSchema: Mapped[FormSchema] = relationship("eyened_orm.form_annotation.FormSchema", back_populates="FormAnnotations")

    PatientID: Mapped[int] = mapped_column(ForeignKey("Patient.PatientID"), index=True)
    Patient: Mapped[Optional[Patient]] = relationship(
        "eyened_orm.patient.Patient", back_populates="FormAnnotations"
    )

    StudyID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Study.StudyID"), nullable=True, index=True
    )
    Study: Mapped[Optional[Study]] = relationship("eyened_orm.study.Study", back_populates="FormAnnotations")

    ImageInstanceID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    ImageInstance: Mapped[Optional[ImageInstance]] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="FormAnnotations"
    )

    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"), index=True)
    Creator: Mapped[Creator] = relationship("eyened_orm.creator.Creator", back_populates="FormAnnotations")

    SubTaskID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("SubTask.SubTaskID"), nullable=True, index=True
    )
    SubTask: Mapped[Optional[SubTask]] = relationship(
        "eyened_orm.task.SubTask", back_populates="FormAnnotations"
    )

    # actual data
    FormData: Mapped[Optional[Dict[str, Any]]] = mapped_column(nullable=True)

    # datetimes
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())
    DateModified: Mapped[Optional[datetime]] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    FormAnnotationReferenceID: Mapped[Optional[int]] = mapped_column(
        ForeignKey("FormAnnotation.FormAnnotationID"), nullable=True
    )

    Inactive: Mapped[bool] = mapped_column(default=False)

    def __repr__(self):
        return f"{self.FormAnnotationID}"

    @classmethod
    def by_schema_and_creator(
        session: Session, schema_name: str, creator_name: str = None
    ) -> List["FormAnnotation"]:
        """
        Get all FormAnnotations for a given schema and optionally filter by creator.
        """
        schema = FormSchema.by_name(session, schema_name)

        if schema is None:
            return []

        q = (
            select(FormAnnotation)
            .where(FormAnnotation.FormSchemaID == schema.FormSchemaID)
            .where(~FormAnnotation.Inactive)
        )
        if creator_name is not None:
            creator = Creator.by_name(session, creator_name)
            q = q.where(FormAnnotation.CreatorID == creator.CreatorID)

        return session.execute(q).scalars().all()

    @classmethod
    def export_formannotations_by_schema(
        cls, schema_name: str, creator_name: str = None
    ) -> DataFrame:
        form_annotations = cls.by_schema_and_creator(schema_name, creator_name)
        data = [form_annotation.flat_data for form_annotation in form_annotations]
        return json_normalize(data)

    @property
    def trash_path(self) -> Path:
        """Return the path to the trash file for this FormAnnotation."""
        return (
            self.config.trash_path / "FormAnnotations" / f"{self.FormAnnotationID}.json"
        )

    @property
    def flat_data(self):
        metadata = {
            "Creator": self.Creator.CreatorName,
            "Created": self.DateInserted,
            "PatientIdentifier": self.Patient.PatientIdentifier,
            "ImageInstance": self.ImageInstanceID,
            "Laterality": (
                str(self.ImageInstance.Laterality.name)
                if self.ImageInstance and self.ImageInstance.Laterality
                else None
            ),
        }
        return metadata | flatten_json(self.FormData)


@event.listens_for(FormAnnotation, "after_delete")
def move_to_trash(mapper, connection, target: FormAnnotation):
    """Move a serialized version of the FormAnnotation to the trash."""
    try:
        trash_path = target.trash_path
        trash_path.parent.mkdir(parents=True, exist_ok=True)
        with open(trash_path, "w") as trash_file:
            json.dump(target.to_dict(), trash_file, indent=4, default=str)
        print(f"FormAnnotation {target.FormAnnotationID} moved to trash: {trash_path}")
    except Exception as e:
        print(f"Failed to move FormAnnotation {target.FormAnnotationID} to trash: {e}")


def flatten_json(
    data: dict | list | str | int | float | bool, parent_key: str = ""
) -> dict:
    if isinstance(data, dict):
        return {
            k: v
            for key, value in data.items()
            for k, v in flatten_json(
                value, f"{parent_key}.{key}" if parent_key else key
            ).items()
        }
    elif isinstance(data, list):
        return {
            k: v
            for i, value in enumerate(data)
            for k, v in flatten_json(value, f"{parent_key}[{i}]").items()
        }
    else:
        return {parent_key: data}
