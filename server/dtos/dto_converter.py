"""
DTO Conversion Service
Converts ORM objects (eyened_orm) into Pydantic GET DTOs defined in server/dtos.
"""

from datetime import datetime
import logging
from typing import TYPE_CHECKING, List, Optional

from eyened_orm import Model, SubTaskState
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, object_session
from sqlalchemy.orm.exc import DetachedInstanceError

from .dtos_aux import CreatorGET, CreatorMeta, TagGET, TagMeta
from .dtos_instances import (
    DeviceMeta,
    ImageGET,
    PatientAttributeValueGET,
    PatientDetailGET,
    PatientMeta,
    ProjectGET,
    ProjectMeta,
    ScanMeta,
    SeriesGET,
    SeriesMeta,
    StudyGET,
    StudyMeta,
)
from .dtos_main import (
    DeviceModelGET,
    FeatureGET,
    FormAnnotationGET,
    FormSchemaGET,
    ModelMeta,
    ModelSegmentationGET,
    SegmentationGET,
)
from .dtos_tasks import SubTaskGET, SubTaskWithImagesGET, TaskDefinitionGET, TaskGET

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from eyened_orm import (
        Creator,
        DeviceModel,
        Feature,
        FormAnnotationTagLink,
        ImageInstance,
        ImageInstanceTagLink,
        ModelSegmentation,
        Patient,
        Project,
        Segmentation,
        SegmentationTagLink,
        Series,
        Study,
        StudyTagLink,
    )
    from eyened_orm import FormAnnotation as FormAnnotationORM
    from eyened_orm import FormSchema as FormSchemaORM
    from eyened_orm import SubTask as SubTaskORM
    from eyened_orm import Tag as TagORM
    from eyened_orm import Task as TaskORM
    from eyened_orm import TaskDefinition as TaskDefinitionORM


class DTOConverter:
    """Service class for converting ORM objects to DTOs."""

    @staticmethod
    def _get_public_id_for_instance_id(
        sess: Optional["Session"], instance_id: Optional[int]
    ) -> Optional[str]:
        if instance_id is None or sess is None:
            return None
        from eyened_orm import ImageInstance

        img = sess.get(ImageInstance, instance_id)
        return img.PublicID if img else None

    # -------------------- Core entities --------------------
    @staticmethod
    def project_to_get(project: "Project") -> ProjectGET:
        """Convert Project ORM object to ProjectGET."""
        return ProjectGET(
            id=project.ProjectID,
            name=project.ProjectName,
            external=(project.External.value == "Y"),
            description=project.Description,
        )

    @staticmethod
    def _registration_attr_to_public_ids(sess: Optional["Session"], value) -> list:
        """Convert legacy ImageInstanceID keys in Registration JSON to PublicID."""
        if not isinstance(value, list):
            return value
        from eyened_orm.utils.registration import (
            build_id_to_public,
            collect_legacy_instance_ids,
            normalize_registration_transforms,
        )

        legacy_ids = collect_legacy_instance_ids(value)
        id_to_public = build_id_to_public(sess, legacy_ids) if sess else {}
        return normalize_registration_transforms(value, id_to_public)

    @staticmethod
    def patient_to_detail_get(
        patient: "Patient", include_attributes: bool = True
    ) -> PatientDetailGET:
        """Convert Patient ORM object to PatientDetailGET."""
        sess = object_session(patient)
        attrs: dict[str, list[PatientAttributeValueGET]] = {}
        if include_attributes:
            for av in getattr(patient, "AttributeValues", []) or []:
                attr_def = getattr(av, "AttributeDefinition", None)
                if not attr_def:
                    continue
                try:
                    value = av.value
                    if attr_def.AttributeName == "Registration":
                        value = DTOConverter._registration_attr_to_public_ids(
                            sess, value
                        )
                    model_meta = None
                    producing_model = getattr(av, "ProducingModel", None)
                    if producing_model is not None:
                        model_meta = DTOConverter.model_to_meta(producing_model)
                    entry = PatientAttributeValueGET(value=value, model=model_meta)
                    attrs.setdefault(attr_def.AttributeName, []).append(entry)
                except Exception:
                    continue

        return PatientDetailGET(
            id=patient.PatientID,
            identifier=patient.PatientIdentifier or "",
            birth_date=patient.BirthDate,
            sex=patient.Sex,
            project=ProjectMeta(
                id=patient.Project.ProjectID,
                name=patient.Project.ProjectName,
            ),
            attrs=attrs,
        )

    @staticmethod
    def link_to_tag_metadata(
        link: "StudyTagLink | ImageInstanceTagLink | SegmentationTagLink | FormAnnotationTagLink",
    ) -> TagMeta:
        """Build TagMetadata from a TagLink using link.Creator and link.DateInserted."""
        return TagMeta(
            id=link.Tag.TagID,
            name=link.Tag.TagName,
            tagger=DTOConverter.creator_to_meta(link.Creator),
            date=link.DateInserted,
            comment=getattr(link, "Comment", None),
        )

    @staticmethod
    def study_to_get(
        study: "Study", include_series: bool = False, with_tag_metadata: bool = False
    ) -> StudyGET:
        """Convert Study ORM object to StudyGET."""
        project_meta = ProjectMeta(
            id=study.Patient.Project.ProjectID,
            name=study.Patient.Project.ProjectName,
        )
        patient = PatientMeta(
            id=study.Patient.PatientID,
            identifier=study.Patient.PatientIdentifier or "",
            birth_date=study.Patient.BirthDate,
            sex=study.Patient.Sex,
        )

        dto = StudyGET(
            id=study.StudyID,
            description=study.StudyDescription,
            date=study.StudyDate,
            round=study.StudyRound,
            age=study.age_years,
            project=project_meta,
            patient=patient,
            tags=[],
        )

        if include_series:
            dto.series = [
                DTOConverter.series_to_get(s)
                for s in (getattr(study, "Series", []) or [])
            ]
        if with_tag_metadata:
            dto.tags = DTOConverter._tags_from_study(study)
        return dto

    @staticmethod
    def series_to_get(series: "Series") -> SeriesGET:
        """Convert Series ORM object to SeriesGET."""
        laterality = (
            series.ImageInstances[0].Laterality if series.ImageInstances else None
        )
        return SeriesGET(
            id=series.SeriesID,
            laterality=laterality,
            series_number=series.SeriesNumber,
            series_instance_uid=series.SeriesInstanceUid or "",
            instance_ids=[
                img.PublicID for img in (getattr(series, "ImageInstances", []) or [])
            ],
        )

    @staticmethod
    def image_instance_to_get(
        image_instance: "ImageInstance",
        with_tag_metadata: bool = False,
        with_segmentations: bool = False,
        with_form_annotations: bool = False,
        with_model_segmentations: bool = False,
    ) -> ImageGET:
        """Convert ImageInstance ORM object to ImageGET."""
        primary_storage = image_instance.primary_storage
        if not primary_storage:
            raise ValueError("ImageInstance has no primary storage")
        object_key = primary_storage.ObjectKey
        data_format = primary_storage.Format
        if data_format == "png_series":
            data_source_id = object_key.split("/")[-1]
        else:
            data_source_id = None
        device_meta = DeviceMeta(
            manufacturer=(
                image_instance.DeviceInstance.DeviceModel.Manufacturer
                if image_instance.DeviceInstance
                and image_instance.DeviceInstance.DeviceModel
                else "Unknown"
            ),
            model=(
                image_instance.DeviceInstance.DeviceModel.ManufacturerModelName
                if image_instance.DeviceInstance
                and image_instance.DeviceInstance.DeviceModel
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
        patient = PatientMeta(
            id=image_instance.Series.Study.Patient.PatientID,
            identifier=image_instance.Series.Study.Patient.PatientIdentifier,
            birth_date=image_instance.Series.Study.Patient.BirthDate,
            sex=image_instance.Series.Study.Patient.Sex,
        )
        study_meta = StudyMeta(
            id=image_instance.Series.Study.StudyID,
            date=image_instance.Series.Study.StudyDate,
        )
        series_meta = SeriesMeta(id=image_instance.Series.SeriesID)

        dto = ImageGET(
            id=image_instance.PublicID,
            sop_instance_uid=image_instance.SOPInstanceUid or "",
            data_format=data_format,
            data_source_id=data_source_id,
            thumbnail_identifier=image_instance.ThumbnailPath or "",
            modality=image_instance.Modality,
            dicom_modality=image_instance.DICOMModality,
            etdrs_field=image_instance.ETDRSField,
            angio_graphy=(
                str(image_instance.Angiography) if image_instance.Angiography else ""
            ),
            laterality=image_instance.Laterality,
            anatomic_region=(
                str(image_instance.AnatomicRegion)
                if image_instance.AnatomicRegion is not None
                else ""
            ),
            rows=image_instance.Rows_y or 0,
            columns=image_instance.Columns_x or 0,
            nr_of_frames=image_instance.NrOfFrames or 1,
            resolution_horizontal=image_instance.ResolutionHorizontal or 0.0,
            resolution_vertical=image_instance.ResolutionVertical or 0.0,
            resolution_axial=image_instance.ResolutionAxial or 0.0,
            cf_roi=image_instance.roi,
            cf_keypoints=image_instance.keypoints,
            cf_quality=image_instance.quality,
            date_inserted=image_instance.DateInserted,
            date_modified=image_instance.DateModified,
            date_preprocessed=image_instance.DatePreprocessed,
            project=project_meta,
            patient=patient,
            study=study_meta,
            series=series_meta,
            device=device_meta,
            scan=scan_meta,
            tags=[],
            model_attrs={},
            attrs={},
        )
        if with_tag_metadata:
            dto.tags = DTOConverter._tags_from_image_instance(image_instance)
        if with_segmentations:
            dto.segmentations = [
                DTOConverter.segmentation_to_get(s, with_tag_metadata=with_tag_metadata)
                for s in (getattr(image_instance, "Segmentations", []) or [])
                if not s.Inactive
            ]
        if with_form_annotations:
            dto.form_annotations = [
                DTOConverter.form_annotation_to_get(
                    fa, with_tag_metadata=with_tag_metadata
                )
                for fa in (getattr(image_instance, "FormAnnotations", []) or [])
                if not fa.Inactive
            ]
        if with_model_segmentations:
            dto.model_segmentations = [
                DTOConverter.model_segmentation_to_get(
                    ms, with_tag_metadata=with_tag_metadata
                )
                for ms in (getattr(image_instance, "ModelSegmentations", []) or [])
            ]
        # attrs / model_attrs: highest-version available row per attribute (see ImageInstance.attrs)
        try:
            dto.attrs, dto.model_attrs = image_instance.attrs
        except DetachedInstanceError:
            logger.warning(
                "ImageInstance %s attrs unavailable (detached session); returning empty",
                getattr(image_instance, "ImageInstanceID", "?"),
                exc_info=True,
            )
            dto.model_attrs = {}
            dto.attrs = {}
        except Exception:
            logger.exception(
                "Failed to build attrs for ImageInstance %s; returning empty",
                getattr(image_instance, "ImageInstanceID", "?"),
            )
            dto.model_attrs = {}
            dto.attrs = {}

        return dto

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
    def creator_to_meta(creator: "Creator") -> CreatorMeta:
        """Convert Creator ORM object to CreatorMetadata."""
        return CreatorMeta(id=creator.CreatorID, name=creator.CreatorName)

    @staticmethod
    def tag_to_get(tag: "TagORM") -> TagGET:
        """Convert Tag ORM object to TagGET."""
        return TagGET(
            id=tag.TagID,
            name=tag.TagName,
            tag_type=tag.TagType,
            description=tag.TagDescription,
            creator=DTOConverter.creator_to_meta(tag.Creator),
            date_inserted=tag.DateInserted,
        )

    @staticmethod
    def device_model_to_get(model: "DeviceModel") -> DeviceModelGET:
        """Convert DeviceModel ORM object to DeviceModelGET."""
        return DeviceModelGET(
            id=model.DeviceModelID,
            manufacturer=model.Manufacturer,
            model=model.ManufacturerModelName,
        )

    @staticmethod
    def model_to_meta(model: "Model") -> ModelMeta:
        """Convert Model ORM object to ModelMeta."""
        return ModelMeta(id=model.ModelID, name=model.ModelName, version=model.Version)

    @staticmethod
    def model_segmentation_to_get(
        ms: "ModelSegmentation", with_tag_metadata: bool = False
    ) -> ModelSegmentationGET:
        """Convert ModelSegmentation ORM object to ModelSegmentationGET."""
        public_image_id = getattr(getattr(ms, "ImageInstance", None), "PublicID", None)
        if public_image_id is None:
            sess = object_session(ms)
            public_image_id = DTOConverter._get_public_id_for_instance_id(
                sess, ms.ImageInstanceID
            )
        # feature best-effort via model.Feature if relationship exists; else omit
        feat = getattr(getattr(ms, "Model", None), "Feature", None)
        if feat is not None:
            feature_get = DTOConverter.feature_to_get(feat)
        else:
            feature_get = FeatureGET(
                id=0,
                name="Unknown feature",
                subfeatures=[],
                subfeature_ids=[],
                date_inserted=datetime.now(),
            )

        if ms.Model is not None:
            creator_meta = DTOConverter.model_to_meta(ms.Model)
        else:
            sess = object_session(ms)
            base_model = sess.get(Model, getattr(ms, "ModelID", None))
            if base_model is not None:
                creator_meta = DTOConverter.model_to_meta(base_model)
            else:
                creator_meta = ModelMeta(
                    id=ms.ModelID, name="Unknown model", version=""
                )

        if public_image_id is None:
            raise ValueError("ModelSegmentation missing ImageInstance PublicID")
        return ModelSegmentationGET(
            id=ms.ModelSegmentationID,
            image_id=public_image_id,
            annotation_type="model_segmentation",
            depth=ms.Depth,
            height=ms.Height,
            width=ms.Width,
            sparse_axis=ms.SparseAxis,
            image_projection_matrix=ms.ImageProjectionMatrix,
            scan_indices=ms.ScanIndices,
            threshold=ms.Threshold,
            data_type=ms.DataType,
            data_representation=ms.DataRepresentation,
            creator=creator_meta,
            feature=feature_get,
            tags=[],  # no tags on ModelSegmentation
            date_inserted=ms.DateInserted,
            date_modified=None,
        )

    @staticmethod
    def _tags_from_form_annotation(annotation: "FormAnnotationORM") -> List[TagMeta]:
        """Extract tags from FormAnnotation using relationship."""
        links = getattr(annotation, "FormAnnotationTagLinks", None) or []
        return [
            DTOConverter.link_to_tag_metadata(link)
            for link in links
            if getattr(link, "Tag", None) and getattr(link, "Creator", None)
        ]

    @staticmethod
    def _tags_from_image_instance(image_instance: "ImageInstance") -> List[TagMeta]:
        """Extract tags from ImageInstance using relationship."""
        links = getattr(image_instance, "ImageInstanceTagLinks", None) or []
        return [
            DTOConverter.link_to_tag_metadata(link)
            for link in links
            if getattr(link, "Tag", None) and getattr(link, "Creator", None)
        ]

    @staticmethod
    def _tags_from_segmentation(segmentation: "Segmentation") -> List[TagMeta]:
        """Extract tags from Segmentation using relationship."""
        links = getattr(segmentation, "SegmentationTagLinks", None) or []
        return [
            DTOConverter.link_to_tag_metadata(link)
            for link in links
            if getattr(link, "Tag", None) and getattr(link, "Creator", None)
        ]

    @staticmethod
    def _tags_from_study(study: "Study") -> List[TagMeta]:
        """Extract tags from Study using relationship."""
        links = getattr(study, "StudyTagLinks", None) or []
        return [
            DTOConverter.link_to_tag_metadata(link)
            for link in links
            if getattr(link, "Tag", None) and getattr(link, "Creator", None)
        ]

    # -------------------- Feature/Segmentation --------------------
    @staticmethod
    def feature_to_get(
        feature: "Feature", segmentation_count: Optional[int] = None
    ) -> FeatureGET:
        """Convert Feature ORM object to FeatureGET."""
        # Prefer a precomputed ORM property if available; otherwise gather from relationship
        child_ids = getattr(feature, "subfeature_ids_list", None)
        if child_ids is None:
            # fallback if your ORM exposes links (rename 'ChildLinks' if different)
            child_ids = [
                link.ChildFeatureID for link in getattr(feature, "ChildLinks", [])
            ]

        subfeatures_dict = feature.subfeatures
        subfeatures = [
            {"index": k, "name": v} for k, v in sorted(subfeatures_dict.items())
        ]

        return FeatureGET(
            id=feature.FeatureID,
            name=feature.FeatureName,
            subfeatures=subfeatures,
            subfeature_ids=child_ids,
            date_inserted=feature.DateInserted,
            segmentation_count=segmentation_count,
        )

    @staticmethod
    def segmentation_to_get(
        seg: "Segmentation", with_tag_metadata: bool = False
    ) -> SegmentationGET:
        """Convert Segmentation ORM object to SegmentationGET."""
        public_image_id = getattr(getattr(seg, "ImageInstance", None), "PublicID", None)
        if public_image_id is None:
            sess = object_session(seg)
            public_image_id = DTOConverter._get_public_id_for_instance_id(
                sess, seg.ImageInstanceID
            )
        if public_image_id is None:
            raise ValueError("Segmentation missing ImageInstance PublicID")
        dto = SegmentationGET(
            id=seg.SegmentationID,
            image_id=public_image_id,
            annotation_type="grader_segmentation",
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
            feature=(
                DTOConverter.feature_to_get(seg.Feature)
                if getattr(seg, "Feature", None)
                else None
            ),  # type: ignore[arg-type]
            creator=(
                DTOConverter.creator_to_meta(seg.Creator)
                if getattr(seg, "Creator", None)
                else None
            ),  # type: ignore[arg-type]
            tags=[],
            date_inserted=seg.DateInserted,
            date_modified=seg.DateModified,
        )
        if with_tag_metadata:
            dto.tags = DTOConverter._tags_from_segmentation(seg)
        return dto

    # -------------------- Form schema/annotations --------------------
    @staticmethod
    def form_schema_to_get(schema: "FormSchemaORM") -> FormSchemaGET:
        """Convert FormSchema ORM object to FormSchemaGET."""
        return FormSchemaGET(
            id=schema.FormSchemaID,
            name=schema.SchemaName,
            schema=schema.Schema,
            entity_type=schema.EntityType,
        )

    @staticmethod
    def form_annotation_to_get(
        annotation: "FormAnnotationORM", with_tag_metadata: bool = False
    ) -> FormAnnotationGET:
        """Convert FormAnnotation ORM object to FormAnnotationGET."""
        # An unloaded ImageInstance means **withheld**, full stop -- this
        # converter never resolves one itself.
        #
        # A FormAnnotation is anchored on PatientID; the image it names has its
        # own, different anchor, so a caller legitimately holding the annotation
        # may hold nothing in the image's project. Only a *scoped* read can
        # decide that, and the only scoped read available here is the one the
        # repository already did. Both ways of resolving it from here --
        # letting ``annotation.ImageInstance`` lazy-load, or looking the id up
        # through ``object_session`` -- go straight to the raw Session with no
        # scope in the chain, and hand back exactly the identifier a scoped
        # loader refused. So the load state is read first and is the whole
        # decision: loaded-and-empty (deliberately withheld by the loader's
        # criteria) and never-loaded (the caller did not ask for it) are
        # answered identically, with None.
        #
        # The consequence is deliberate: a caller that serialises an annotation
        # without asking its repository to load the image emits ``image_id:
        # None`` for an image it could have shown. That is a visible functional
        # degradation, and it is the fail-closed direction -- the alternative
        # fails open, silently, on a caller that forgot.
        state = sa_inspect(annotation, raiseerr=False)
        loaded = state is not None and "ImageInstance" not in state.unloaded
        image = annotation.ImageInstance if loaded else None
        public_image_id = getattr(image, "PublicID", None)

        if annotation.ImageInstanceID is not None:
            if image is not None and public_image_id is None:
                # The loader handed back a row with no PublicID: nothing
                # withheld this, so it is a genuine data error.
                raise ValueError("FormAnnotation missing ImageInstance PublicID")
            obj_type = "image_instance"
        elif annotation.StudyID is not None:
            obj_type = "study"
        else:
            obj_type = "patient"

        dto = FormAnnotationGET(
            id=annotation.FormAnnotationID,
            annotation_type="grader_form",
            form_schema_id=annotation.FormSchemaID,
            patient_id=annotation.PatientID,
            study_id=annotation.StudyID,
            image_id=public_image_id,
            laterality=annotation.Laterality,
            sub_task_id=annotation.SubTaskID,
            form_data=annotation.FormData,
            form_annotation_reference_id=annotation.FormAnnotationReferenceID,
            object_type=obj_type,  # type: ignore[assignment]
            tags=[],
            creator=(
                DTOConverter.creator_to_meta(annotation.Creator)
                if getattr(annotation, "Creator", None)
                else None
            ),
            date_inserted=annotation.DateInserted,
            date_modified=annotation.DateModified,
        )
        if with_tag_metadata:
            dto.tags = DTOConverter._tags_from_form_annotation(annotation)
        return dto

    # -------------------- Task system --------------------
    @staticmethod
    def task_definition_to_get(taskdef: "TaskDefinitionORM") -> TaskDefinitionGET:
        """Convert TaskDefinition ORM object to TaskDefinitionGET."""
        return TaskDefinitionGET(
            id=taskdef.TaskDefinitionID,
            name=taskdef.TaskDefinitionName,
            config=taskdef.TaskConfig or {},
            date_inserted=taskdef.DateInserted,
        )

    @staticmethod
    def task_to_get(
        task: "TaskORM",
        *,
        num_tasks: int | None = None,
        num_tasks_ready: int | None = None,
        projects: list[tuple[int, str]],
    ) -> TaskGET:
        """Convert Task ORM object to TaskGET.

        ``projects`` is required and takes no default on purpose. The DTO field
        defaults to ``[]``, so a call site that forgot to pass the task's
        projects would answer "this task spans nothing" for a task spanning
        two -- the exact wrong answer, delivered confidently, to the admin this
        field exists to warn. Requiring it turns that omission into a
        TypeError.
        """
        if num_tasks is None or num_tasks_ready is None:
            subs = getattr(task, "SubTasks", []) or []
            if num_tasks is None:
                num_tasks = len(subs)
            if num_tasks_ready is None:
                num_tasks_ready = sum(
                    1 for st in subs if st.TaskState == SubTaskState.Ready
                )

        return TaskGET(
            id=task.TaskID,
            name=task.TaskName,
            description=task.Description,
            contact_id=task.ContactID,
            task_definition_id=task.TaskDefinitionID,
            date_inserted=task.DateInserted,
            num_tasks=num_tasks,
            num_tasks_ready=num_tasks_ready,
            creator=(
                DTOConverter.creator_to_meta(task.Creator)
                if getattr(task, "Creator", None)
                else None
            ),
            task_state=getattr(task, "TaskState", None),
            task_definition=DTOConverter.task_definition_to_get(task.TaskDefinition),
            projects=[
                ProjectMeta(id=project_id, name=project_name)
                for project_id, project_name in projects
            ],
        )

    @staticmethod
    def subtask_to_get(subtask: "SubTaskORM") -> SubTaskGET:
        """Convert SubTask ORM object to SubTaskGET."""
        return SubTaskGET(
            id=subtask.SubTaskID,
            task_id=subtask.TaskID,
            task_state=subtask.TaskState,
            creator_id=subtask.CreatorID,
            creator=(
                DTOConverter.creator_to_meta(subtask.Creator)
                if getattr(subtask, "Creator", None)
                else None
            ),
            comments=subtask.Comments,
        )

    @staticmethod
    def subtask_with_images_to_get(subtask: "SubTaskORM") -> SubTaskWithImagesGET:
        """Convert SubTask ORM object to SubTaskWithImagesGET, including images."""
        images = [
            DTOConverter.image_instance_to_get(link.ImageInstance)
            for link in (getattr(subtask, "SubTaskImageLinks", None) or [])
            if getattr(link, "ImageInstance", None)
        ]
        return SubTaskWithImagesGET(
            id=subtask.SubTaskID,
            task_id=subtask.TaskID,
            task_state=subtask.TaskState,
            creator_id=subtask.CreatorID,
            creator=(
                DTOConverter.creator_to_meta(subtask.Creator)
                if getattr(subtask, "Creator", None)
                else None
            ),
            comments=subtask.Comments,
            images=images,
        )
