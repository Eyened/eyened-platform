"""
DTO Conversion Service
Converts ORM objects (eyened_orm) into Pydantic GET DTOs defined in server/dtos.
"""

from typing import TYPE_CHECKING, Optional, List

from .dtos_instances import (
    ProjectGET,
    PatientGET,
    StudyGET,
    SeriesGET,
    InstanceGET,
    ProjectMeta,
    PatientMeta,
    StudyMeta,
    SeriesMeta,
    DeviceMeta,
    ScanMeta,
)
from .dtos_aux import CreatorGET, TagGET
from .dtos_main import FeatureGET, SegmentationGET, FormSchemaGET, FormAnnotationGET
from .dtos_tasks import TaskDefinitionGET, TaskStateGET, TaskGET, SubTaskGET

if TYPE_CHECKING:
    from eyened_orm import (
        Study,
        Patient,
        Series,
        ImageInstance,
        Project,
        Creator,
        DeviceModel,
        DeviceInstance,
        Scan,
        Tag as TagORM,
        Feature,
        Segmentation,
        FormSchema as FormSchemaORM,
        FormAnnotation as FormAnnotationORM,
        TaskDefinition as TaskDefinitionORM,
        TaskState as TaskStateORM,
        Task as TaskORM,
        SubTask as SubTaskORM,
    )


class DTOConverter:
    """Service class for converting ORM objects to DTOs."""

    # -------------------- Core entities --------------------
    @staticmethod
    def project_to_get(project: "Project") -> ProjectGET:
        """Convert Project ORM object to ProjectGET."""
        return ProjectGET(
            id=project.ProjectID,
            name=project.ProjectName,
            external=project.External.value == 1,
            description=project.Description,
        )

    @staticmethod
    def patient_to_get(patient: "Patient") -> PatientGET:
        """Convert Patient ORM object to PatientGET."""
        sex_str: Optional[str] = None
        if patient.Sex is not None:
            sex_str = patient.Sex.name
        return PatientGET(
            id=patient.PatientID,
            identifier=patient.PatientIdentifier or "",
            birth_date=patient.BirthDate,
            sex=sex_str,
        )

    @staticmethod
    def study_to_get(study: "Study") -> StudyGET:
        """Convert Study ORM object to StudyGET."""
        return StudyGET(
            id=study.StudyID,
            description=study.StudyDescription,
            date=study.StudyDate,
            study_instance_uid=study.StudyInstanceUid,
        )

    @staticmethod
    def series_to_get(series: "Series") -> SeriesGET:
        """Convert Series ORM object to SeriesGET."""
        return SeriesGET(
            id=series.SeriesID,
            series_number=series.SeriesNumber,
            series_instance_uid=series.SeriesInstanceUid or "",
        )

    @staticmethod
    def image_instance_to_get(image_instance: "ImageInstance") -> InstanceGET:
        """Convert ImageInstance ORM object to InstanceGET."""
        device_meta = DeviceMeta(
            manufacturer=(
                image_instance.DeviceInstance.DeviceModel.Manufacturer
                if image_instance.DeviceInstance and image_instance.DeviceInstance.DeviceModel
                else "Unknown"
            ),
            model=(
                image_instance.DeviceInstance.DeviceModel.ManufacturerModelName
                if image_instance.DeviceInstance and image_instance.DeviceInstance.DeviceModel
                else "Unknown"
            ),
        )

        scan_meta = ScanMeta(
            mode=(image_instance.Scan.ScanMode if image_instance.Scan else "Unknown")
        )

        project_meta = ProjectMeta(
            id=image_instance.Series.Study.Patient.Project.ProjectID,
            name=image_instance.Series.Study.Patient.Project.ProjectName,
        )
        patient_meta = PatientMeta(
            id=image_instance.Series.Study.Patient.PatientID,
            identifier=image_instance.Series.Study.Patient.PatientIdentifier,
            birth_date=image_instance.Series.Study.Patient.BirthDate,
        )
        study_meta = StudyMeta(
            id=image_instance.Series.Study.StudyID,
            date=image_instance.Series.Study.StudyDate,
        )
        series_meta = SeriesMeta(id=image_instance.Series.SeriesID)

        return InstanceGET(
            id=image_instance.ImageInstanceID,
            sop_instance_uid=image_instance.SOPInstanceUid or "",
            dataset_identifier=image_instance.DatasetIdentifier,
            thumbnail_identifier=image_instance.ThumbnailPath or "",
            thumbnail_path=image_instance.ThumbnailPath or "",
            modality=image_instance.Modality.name if image_instance.Modality else "",
            dicom_modality=(
                image_instance.DICOMModality.name if image_instance.DICOMModality else ""
            ),
            etdrs_field=image_instance.ETDRSField.name if image_instance.ETDRSField else "",
            angio_graphy=str(image_instance.Angiography) if image_instance.Angiography else "",
            laterality=image_instance.Laterality.name if image_instance.Laterality else "L",
            anatomic_region=str(image_instance.AnatomicRegion) if image_instance.AnatomicRegion is not None else "",
            rows=image_instance.Rows_y or 0,
            columns=image_instance.Columns_x or 0,
            nr_of_frames=image_instance.NrOfFrames or 1,
            resolution_horizontal=image_instance.ResolutionHorizontal or 0.0,
            resolution_vertical=image_instance.ResolutionVertical or 0.0,
            resolution_axial=image_instance.ResolutionAxial or 0.0,
            cf_roi=image_instance.CFROI,
            cf_keypoints=image_instance.CFKeypoints,
            cf_quality=image_instance.CFQuality,
            date_inserted=image_instance.DateInserted,
            date_modified=image_instance.DateModified,
            date_preprocessed=image_instance.DatePreprocessed,
            project=project_meta,
            patient=patient_meta,
            study=study_meta,
            series=series_meta,
            device=device_meta,
            scan=scan_meta,
        )

    # -------------------- Auxiliary entities --------------------
    @staticmethod
    def creator_to_get(creator: "Creator") -> CreatorGET:
        """Convert Creator ORM object to CreatorGET."""
        return CreatorGET(
            id=creator.CreatorID,
            name=creator.CreatorName,
            msn=getattr(creator, "EmployeeIdentifier", None),
            is_human=creator.IsHuman,
            description=creator.Description,
            version=str(creator.Version) if creator.Version is not None else None,
            role=creator.Role,
            date_inserted=creator.DateInserted,
        )

    @staticmethod
    def tag_to_get(tag: "TagORM") -> TagGET:
        """Convert Tag ORM object to TagGET."""
        return TagGET(id=tag.TagID, name=tag.TagName)

    # -------------------- Feature/Segmentation --------------------
    @staticmethod
    def feature_to_get(feature: "Feature") -> FeatureGET:
        """Convert Feature ORM object to FeatureGET."""
        return FeatureGET(
            id=feature.FeatureID,
            name=feature.FeatureName,
            date_inserted=feature.DateInserted,
        )

    @staticmethod
    def segmentation_to_get(seg: "Segmentation") -> SegmentationGET:
        """Convert Segmentation ORM object to SegmentationGET."""
        # Tags relationship may not be present directly; default to empty list
        tags: List[TagGET] = []
        return SegmentationGET(
            id=seg.SegmentationID,
            depth=seg.Depth,
            height=seg.Height,
            width=seg.Width,
            sparse_axis=seg.SparseAxis,
            image_projection_matrix=seg.ImageProjectionMatrix,
            scan_indices=seg.ScanIndices,
            threshold=seg.Threshold,
            reference_segmentation_id=seg.ReferenceSegmentationID,
            data_type=seg.DataType,
            data_representation=seg.DataRepresentation,
            feature=DTOConverter.feature_to_get(seg.Feature) if getattr(seg, "Feature", None) else None,  # type: ignore[arg-type]
            creator=DTOConverter.creator_to_get(seg.Creator) if getattr(seg, "Creator", None) else None,  # type: ignore[arg-type]
            tags=tags,
            date_inserted=seg.DateInserted,
            date_modified=seg.DateModified,
        )

    # -------------------- Form schema/annotations --------------------
    @staticmethod
    def form_schema_to_get(schema: "FormSchemaORM") -> FormSchemaGET:
        """Convert FormSchema ORM object to FormSchemaGET."""
        return FormSchemaGET(id=schema.FormSchemaID, name=schema.SchemaName, schema=schema.Schema)

    @staticmethod
    def form_annotation_to_get(annotation: "FormAnnotationORM") -> FormAnnotationGET:
        """Convert FormAnnotation ORM object to FormAnnotationGET."""
        if annotation.ImageInstanceID is not None:
            obj_type = "image_instance"
        elif annotation.StudyID is not None:
            obj_type = "study"
        else:
            obj_type = "patient"

        return FormAnnotationGET(
            id=annotation.FormAnnotationID,
            form_schema_id=annotation.FormSchemaID,
            patient_id=annotation.PatientID,
            study_id=annotation.StudyID,
            image_instance_id=annotation.ImageInstanceID,
            creator_id=annotation.CreatorID,
            sub_task_id=annotation.SubTaskID,
            form_data=annotation.FormData,
            form_annotation_reference_id=annotation.FormAnnotationReferenceID,
            inactive=annotation.Inactive,
            object_type=obj_type,  # type: ignore[assignment]
            patient=(DTOConverter.patient_to_get(annotation.Patient) if getattr(annotation, "Patient", None) else None),
            study=(DTOConverter.study_to_get(annotation.Study) if getattr(annotation, "Study", None) else None),
            image_instance=(DTOConverter.image_instance_to_get(annotation.ImageInstance) if getattr(annotation, "ImageInstance", None) else None),
            date_inserted=annotation.DateInserted,
            date_modified=annotation.DateModified,
        )

    # -------------------- Task system --------------------
    @staticmethod
    def task_definition_to_get(taskdef: "TaskDefinitionORM") -> TaskDefinitionGET:
        """Convert TaskDefinition ORM object to TaskDefinitionGET."""
        return TaskDefinitionGET(
            id=taskdef.TaskDefinitionID,
            name=taskdef.TaskDefinitionName,
            date_inserted=taskdef.DateInserted,
        )

    @staticmethod
    def task_state_to_get(state: "TaskStateORM") -> TaskStateGET:
        """Convert TaskState ORM object to TaskStateGET."""
        return TaskStateGET(id=state.TaskStateID, name=state.TaskStateName)

    @staticmethod
    def task_to_get(task: "TaskORM") -> TaskGET:
        """Convert Task ORM object to TaskGET."""
        return TaskGET(
            id=task.TaskID,
            name=task.TaskName,
            description=task.Description,
            contact_id=task.ContactID,
            task_definition_id=task.TaskDefinitionID,
            task_state_id=task.TaskStateID if getattr(task, "TaskStateID", None) is not None else (task.TaskState.TaskStateID if getattr(task, "TaskState", None) else None),  # type: ignore[union-attr]
            date_inserted=task.DateInserted,
        )

    @staticmethod
    def subtask_to_get(subtask: "SubTaskORM") -> SubTaskGET:
        """Convert SubTask ORM object to SubTaskGET."""
        return SubTaskGET(
            id=subtask.SubTaskID,
            task_id=subtask.TaskID,
            task_state_id=subtask.TaskStateID,
            creator_id=subtask.CreatorID,
        )
