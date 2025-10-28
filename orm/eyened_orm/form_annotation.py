from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

from pandas import DataFrame, json_normalize
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (
        Creator,
        FormAnnotationTagLink,
        ImageInstance,
        Patient,
        Study,
        SubTask,
    )


class FormSchema(Base):
    __tablename__ = "FormSchema"
    _name_column: ClassVar[str] = "SchemaName"

    FormSchemaID: Mapped[int] = mapped_column(primary_key=True)
    SchemaName: Mapped[str] = mapped_column(String(255), unique=True)
    Schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    FormAnnotations: Mapped[List["FormAnnotation"]] = relationship("eyened_orm.form_annotation.FormAnnotation", back_populates="FormSchema")


class FormAnnotation(Base):
    __tablename__ = "FormAnnotation"

    FormAnnotationID: Mapped[int] = mapped_column(primary_key=True)

    FormSchemaID: Mapped[int] = mapped_column(ForeignKey("FormSchema.FormSchemaID"))
    PatientID: Mapped[int] = mapped_column(ForeignKey("Patient.PatientID"))
    StudyID: Mapped[Optional[int]] = mapped_column(ForeignKey("Study.StudyID"))
    ImageInstanceID: Mapped[Optional[int]] = mapped_column(ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE"))
    CreatorID: Mapped[int] = mapped_column(ForeignKey("Creator.CreatorID"))
    SubTaskID: Mapped[Optional[int]] = mapped_column(ForeignKey("SubTask.SubTaskID", ondelete="SET NULL"))
    FormData: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    FormAnnotationReferenceID: Mapped[Optional[int]] = mapped_column(ForeignKey("FormAnnotation.FormAnnotationID", ondelete="CASCADE"), index=True)
    Inactive: Mapped[bool] = mapped_column(default=False)

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())
    DateModified: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    FormSchema: Mapped["FormSchema"] = relationship("eyened_orm.form_annotation.FormSchema", back_populates="FormAnnotations")
    Patient: Mapped["Patient"] = relationship("eyened_orm.patient.Patient", back_populates="FormAnnotations")
    Study: Mapped["Study"] = relationship("eyened_orm.study.Study", back_populates="FormAnnotations")
    ImageInstance: Mapped["ImageInstance"] = relationship("eyened_orm.image_instance.ImageInstance", back_populates="FormAnnotations")
    Creator: Mapped["Creator"] = relationship("eyened_orm.creator.Creator", back_populates="FormAnnotations")
    SubTask: Mapped["SubTask"] = relationship("eyened_orm.task.SubTask", back_populates="FormAnnotations")
    FormAnnotationTagLinks: Mapped[List["FormAnnotationTagLink"]] = relationship("eyened_orm.tag.FormAnnotationTagLink", back_populates="FormAnnotation", passive_deletes=True, lazy="selectin")

    @classmethod
    def by_schema_and_creator(cls, session: Session, schema_name: str, creator_name: str = None, filterInactive: bool = True, **kwargs) -> List["FormAnnotation"]:
        """Get all FormAnnotations for a given schema; optionally filter by creator."""
        from eyened_orm import Creator, FormSchema

        schema = FormSchema.by_name(session, schema_name)

        if schema is None:
            return []

        # Build filter conditions
        filter_kwargs = {"FormSchemaID": schema.FormSchemaID, **kwargs}
        if filterInactive:
            filter_kwargs["Inactive"] = False

        # Add creator filter if provided
        if creator_name is not None:
            creator = Creator.by_name(session, creator_name)
            filter_kwargs["CreatorID"] = creator.CreatorID

        return FormAnnotation.by_columns(session, **filter_kwargs)

    @classmethod
    def export_formannotations_by_schema(cls, session: Session, schema_name: str, creator_name: str = None) -> DataFrame:
        form_annotations = cls.by_schema_and_creator(session, schema_name, creator_name)
        data = [form_annotation.flat_data for form_annotation in form_annotations]
        return json_normalize(data)

    @property
    def flat_data(self):
        metadata = {
            "Creator": self.Creator.CreatorName,
            "Created": self.DateInserted,
            "PatientIdentifier": self.Patient.PatientIdentifier,
            "ImageInstance": self.ImageInstanceID,
            "Laterality": (str(self.ImageInstance.Laterality.name) if self.ImageInstance and self.ImageInstance.Laterality else None),
        }
        return metadata | flatten_json(self.FormData)


def flatten_json(data: dict | list | str | int | float | bool, parent_key: str = "") -> dict:
    if isinstance(data, dict):
        return {k: v for key, value in data.items() for k, v in flatten_json(value, f"{parent_key}.{key}" if parent_key else key).items()}
    elif isinstance(data, list):
        return {k: v for i, value in enumerate(data) for k, v in flatten_json(value, f"{parent_key}[{i}]").items()}
    else:
        return {parent_key: data}
