import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List

from pandas import DataFrame, json_normalize
from sqlalchemy import Column, DateTime, event, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (Creator, FormSchema, ImageInstance, Patient, Study,
                            SubTask)


class FormSchemaBase(Base):
    SchemaName: str = Field(max_length=45, unique=True)
    Schema: Dict[str, Any] | None = Field(sa_column=Column(JSON), default=None)

class FormSchema(FormSchemaBase, table=True):
    __tablename__ = "FormSchema"
    _name_column: ClassVar[str] = "SchemaName"

    FormSchemaID: int = Field(primary_key=True)

    FormAnnotations: List["FormAnnotation"] = Relationship(back_populates="FormSchema")


class FormAnnotationBase(Base):
    FormSchemaID: int = Field(foreign_key="FormSchema.FormSchemaID")
    PatientID: int = Field(foreign_key="Patient.PatientID")
    StudyID: int | None = Field(foreign_key="Study.StudyID", default=None)
    ImageInstanceID: int | None = Field(foreign_key="ImageInstance.ImageInstanceID", default=None)
    CreatorID: int = Field(foreign_key="Creator.CreatorID")
    SubTaskID: int | None = Field(foreign_key="SubTask.SubTaskID", default=None)
    FormData: Dict[str, Any] | None = Field(sa_column=Column(JSON), default=None)
    FormAnnotationReferenceID: int | None = Field(foreign_key="FormAnnotation.FormAnnotationID", default=None)
    Inactive: bool = False
    
class FormAnnotation(FormAnnotationBase, table=True):
    __tablename__ = "FormAnnotation"

    FormAnnotationID: int = Field(primary_key=True)
    DateInserted: datetime = Field(default_factory=datetime.now)
    DateModified: datetime | None = Field(
        sa_column=Column(
            DateTime, server_default=func.now(), server_onupdate=func.now()
        )
    )

    FormSchema: "FormSchema" = Relationship(back_populates="FormAnnotations")
    Patient: "Patient" = Relationship(back_populates="FormAnnotations")
    Study: "Study" = Relationship(back_populates="FormAnnotations")
    ImageInstance: "ImageInstance" = Relationship(back_populates="FormAnnotations")
    Creator: "Creator" = Relationship(back_populates="FormAnnotations")
    SubTask: "SubTask" = Relationship(back_populates="FormAnnotations")


    @classmethod
    def by_schema_and_creator(
        cls,
        session: Session,
        schema_name: str,
        creator_name: str = None,
        filterInactive: bool = True,
        **kwargs
    ) -> List["FormAnnotation"]:
        """
        Get all FormAnnotations for a given schema and optionally filter by creator.
        Additional filters can be passed as keyword arguments.
        """
        from eyened_orm import Creator, FormSchema
        schema = FormSchema.by_name(session, schema_name)

        if schema is None:
            return []

        # Build filter conditions
        filter_kwargs = {
            "FormSchemaID": schema.FormSchemaID,
            **kwargs
        }
        if filterInactive:
            filter_kwargs["Inactive"] = False

        # Add creator filter if provided
        if creator_name is not None:
            creator = Creator.by_name(session, creator_name)
            filter_kwargs["CreatorID"] = creator.CreatorID

        return FormAnnotation.by_columns(session, **filter_kwargs)

    @classmethod
    def export_formannotations_by_schema(
        cls, session: Session, schema_name: str, creator_name: str = None
    ) -> DataFrame:
        form_annotations = cls.by_schema_and_creator(session, schema_name, creator_name)
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
