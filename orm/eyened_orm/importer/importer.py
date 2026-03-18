import warnings
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
import pandas as pd
from typing import TypeVar
from eyened_orm.base import Base

T = TypeVar("T", bound=Base)

from eyened_orm import (
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
)
from eyened_orm.attributes import AttributeDataType, AttributeDefinition, AttributeValue

from eyened_orm.base import Base
from eyened_orm.image_instance import (
    DeviceInstance,
    DeviceModel,
    ImageStorage,
    Modality,
    Scan,
    SourceInfo,
    StorageBackend,
)
from eyened_orm.importer.thumbnails import update_thumbnails
from eyened_orm.project import ExternalEnum
from eyened_orm import Segmentation, Creator, Feature

from .importer_dtos import (
    ImageImport,
    InstancePOSTFlat,
    PatientImport,
    SegmentationImport,
    SeriesImport,
    StudyImport,
)


class Importer:
    def __init__(
        self,
        session,
        create_patients: bool = False,
        create_studies: bool = False,
        create_series: bool = True,
        create_projects: bool = False,
        create_segmentations: bool = False,
        run_ai_models: bool = False,
        generate_thumbnails: bool = True,
    ):
        """
        Initialize the Importer with database session and data to import.

        Parameters:
        -----------
        session : SQLAlchemy session
            Database session to use for the import
        create_patients : bool, default=False
            If True, create patients when they don't exist
        create_studies : bool, default=False
            If True, create studies when they don't exist
        create_series : bool, default=False
            If True, create series when they don't exist
        create_projects : bool, default=False
            If True, create project when it doesn't exist
        create_segmentations : bool, default=False
            If True, create segmentations when they don't exist
        run_ai_models : bool, default=False
            If True, run AI models on the images after import
        generate_thumbnails : bool, default=True
            If True, generate thumbnails for the images after import
        """
        self.session = session
        self.create_patients = create_patients
        self.create_studies = create_studies
        self.create_series = create_series
        self.create_projects = create_projects
        self.create_segmentations = create_segmentations
        self.run_ai_models = run_ai_models
        self.generate_thumbnails = generate_thumbnails

        self.created_entities = set()
        self.existing_entities = set()
        self.pending_segmentation_writes = []

    def _ensure_entity(
        self,
        model_cls: type[T],
        match_by: Dict,
        create_allowed: bool = True,
        create_kwargs: Dict | None = None,
        must_match: Dict | None = None,
        update_values: Dict | None = None,
    ) -> T:
        """
        Resolve an entity by keys and create it if needed using Base.get_or_create.
        """

        existed_before = True
        if create_allowed:
            existed_before = model_cls.by_column(self.session, **match_by) is not None
            entity = model_cls.get_or_create(
                self.session,
                match_by=match_by,
                create_kwargs=create_kwargs,
                must_match=must_match,
                update_values=update_values,
            )
        else:
            entity = model_cls.by_column(self.session, **match_by)
            if entity is None:
                raise RuntimeError(
                    f"Entity of type {model_cls.__name__} with keys {match_by} not found and create_allowed=False"
                )
            existed_before = True

        self._track_entity_state(entity, is_new=not existed_before)
        return entity

    def _track_entity_state(self, entity: Base, is_new: bool):
        if is_new:
            self.created_entities.add(entity)
            self.existing_entities.discard(entity)
        else:
            self.existing_entities.add(entity)
            self.created_entities.discard(entity)

    @property
    def _all_entities(self) -> set[Base]:
        return self.created_entities | self.existing_entities

    def init_objects(self, data: List[PatientImport]):
        """
        Traverses the data structure and creates patient, study and series objects.

        Creates the hierarchy from project down to series objects based on the data
        structure and configuration.

        Parameters:
        ----------
        data : List[PatientImport]
            List of PatientImport objects

        Returns:
        --------
        List[Project]
            The project objects (either found or created)
        """
        # Clear collections before starting
        self.created_entities = set()
        self.existing_entities = set()
        self.pending_segmentation_writes = []

        for patient_item in data:
            self._import_patient_tree(patient_item)

    def _import_patient_tree(self, patient_item: PatientImport):
        project = self._ensure_project(patient_item)
        patient = self._ensure_patient(project, patient_item)

        for study_item in patient_item.studies:
            self._import_study_tree(patient, study_item)

    def _import_study_tree(self, patient: Patient, study_item: StudyImport):
        study = self._ensure_study(patient, study_item)

        for series_item in study_item.series:
            self._import_series_tree(study, series_item)

    def _import_series_tree(self, study: Study, series_item: SeriesImport):
        series = self._ensure_series(study, series_item)

        for image_item in series_item.images:
            self._import_image(series, image_item)

    def _import_image(self, series: Series, image_item: ImageImport):
        image = self.create_image(series, image_item)

        if image_item.attributes:
            self._process_attributes(image, image_item.attributes)

        if image_item.segmentations:
            self._process_segmentations(image, image_item.segmentations)

    def _ensure_project(self, patient_item: PatientImport) -> Project:
        return self._ensure_entity(
            Project,
            match_by={"ProjectName": patient_item.project_name},
            create_allowed=self.create_projects,
            create_kwargs={"External": ExternalEnum.Y},
        )

    def _ensure_patient(self, project: Project, patient_item: PatientImport) -> Patient:
        return self._ensure_entity(
            Patient,
            match_by={
                "ProjectID": project.ProjectID,
                "PatientIdentifier": patient_item.patient_identifier,
            },
            create_allowed=self.create_patients,
            create_kwargs={
                "Sex": patient_item.sex,
                "BirthDate": patient_item.birth_date,
            },
        )

    def _ensure_study(self, patient: Patient, study_item: StudyImport) -> Study:
        return self._ensure_entity(
            Study,
            match_by={
                "PatientID": patient.PatientID,
                "StudyDate": study_item.study_date,
            },
            create_allowed=self.create_studies,
            create_kwargs={
                "StudyDescription": study_item.description,
            },
        )

    def _ensure_series(self, study: Study, series_item: SeriesImport) -> Series:
        return self._ensure_entity(
            Series,
            match_by={
                "StudyID": study.StudyID,
                "SeriesID": series_item.series_id,
            },
            create_allowed=self.create_series,
            create_kwargs={
                "SeriesNumber": series_item.series_number,
                "SeriesInstanceUid": series_item.series_instance_uid,
            },
        )

    def _process_attributes(self, image: ImageInstance, attributes_data: Dict):
        for name, value in attributes_data.items():
            dtype = AttributeDefinition.infer_attribute_data_type(value)
            attr_def = self._ensure_entity(
                AttributeDefinition,
                match_by={"AttributeName": name},
                create_kwargs={"AttributeDataType": dtype},
            )

            attr_val = self._ensure_entity(
                AttributeValue,
                match_by={
                    "AttributeID": attr_def.AttributeID,
                    "ImageInstanceID": image.ImageInstanceID,
                },
                update_values={"value": value},
            )

    def _process_segmentations(
        self, image: ImageInstance, segmentations_data: List[SegmentationImport]
    ):
        for item in segmentations_data:
            data = item.data
            creator = self._ensure_entity(
                Creator,
                match_by={"CreatorName": item.creator_name},
                create_allowed=False,
            )
            feature = self._ensure_entity(
                Feature,
                match_by={"FeatureName": item.feature_name},
                create_allowed=False,
            )

            seg = self._ensure_entity(
                Segmentation,
                match_by={
                    "ImageInstanceID": image.ImageInstanceID,
                    "CreatorID": creator.CreatorID,
                    "FeatureID": feature.FeatureID,
                    "ReferenceSegmentationID": item.reference_segmentation_id,
                },
                update_values={
                    "DataType": item.data_type,
                    "DataRepresentation": item.data_representation,
                    "Depth": item.depth,
                    "Height": item.height,
                    "Width": item.width,
                    "SparseAxis": item.sparse_axis,
                    "ImageProjectionMatrix": item.image_projection_matrix,
                    "ScanIndices": item.scan_indices,
                    "Threshold": item.threshold,
                },
                create_allowed=self.create_segmentations,
            )
            self._apply_segmentation_defaults(seg, data, image)
            self.pending_segmentation_writes.append((seg, data))

    @staticmethod
    def _apply_segmentation_defaults(
        seg: Segmentation, data: np.ndarray, image: ImageInstance
    ):
        if seg.DataType is None:
            seg.DataType = Segmentation.infer_data_type(data)

        if seg.Width is None:
            seg.Width = image.Columns_x
        if seg.Height is None:
            seg.Height = image.Rows_y
        if seg.Depth is None:
            seg.Depth = image.NrOfFrames if image.NrOfFrames else 1

    @staticmethod
    def infer_storage_format(object_key: str) -> str:
        suffix = Path(object_key).suffix.lower()
        if suffix in {".dcm", ".dicom"}:
            return "dicom"
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".mhd":
            return "mhd"
        if suffix == "":
            return "png_series"
        return "binary"

    def create_image(self, series: Series, image_data: ImageImport) -> ImageInstance:
        object_key = image_data.object_key

        storage_backend = self._ensure_entity(
            StorageBackend,
            match_by={"Key": image_data.storage_backend_key},
            create_kwargs={"Kind": "local"},
        )

        device_model = self._ensure_entity(
            DeviceModel,
            match_by={
                "Manufacturer": image_data.device_manufacturer or "Unknown",
                "ManufacturerModelName": image_data.device_model or "Unknown",
            },
        )
        device_instance = self._ensure_entity(
            DeviceInstance,
            match_by={
                "DeviceModelID": device_model.DeviceModelID,
                "SerialNumber": image_data.device_serial_number,
            },
            create_kwargs={
                "Description": image_data.device_description or "Unknown",
            },
        )

        try:
            modality = image_data.modality
        except ValueError:
            warnings.warn(
                f"Could not map string '{image_data.modality}' to Modality enum. Leaving as None."
            )
            modality = None

        scan = None
        if image_data.scan_mode:
            scan = self._ensure_entity(
                Scan,
                match_by={"ScanMode": image_data.scan_mode},
            )

        im = ImageInstance(
            SOPInstanceUid=image_data.sop_instance_uid,
            Modality=modality,
            DICOMModality=image_data.dicom_modality,
            ETDRSField=image_data.etdrs_field,
            Laterality=image_data.laterality,
            Rows_y=image_data.height,
            Columns_x=image_data.width,
            NrOfFrames=image_data.depth,
            ResolutionHorizontal=image_data.resolution_horizontal,
            ResolutionVertical=image_data.resolution_vertical,
            ResolutionAxial=image_data.resolution_axial,
            OldPath=image_data.old_path,
            DatasetIdentifier="",
            Series=series,
            SourceInfoID=image_data.source_info_id,
            DeviceInstance=device_instance,
            Scan=scan,
            # New fields
            AnatomicRegion=image_data.anatomic_region,
            AcquisitionDateTime=image_data.acquisition_date_time,
            Angiography=image_data.angiography,
            SamplesPerPixel=image_data.samples_per_pixel,
            HorizontalFieldOfView=image_data.horizontal_field_of_view,
            SOPClassUid=image_data.sop_class_uid,
            PhotometricInterpretation=image_data.photometric_interpretation,
            PupilDilated=image_data.pupil_dilated,
            FDAIdentifier=image_data.fda_identifier,
        )
        self.session.add(im)
        self.session.flush([im])
        self._track_entity_state(im, is_new=True)

        image_storage = ImageStorage(
            ImageInstance=im,
            StorageBackend=storage_backend,
            ObjectKey=object_key,
            Format=self.infer_storage_format(object_key),
            IsPrimary=True,
        )
        self.session.add(image_storage)
        self.session.flush([image_storage])
        self._track_entity_state(image_storage, is_new=True)

        return im

    def post_insert(self):
        """
        Here we run preprocessing, AI models and generate thumbnails
        The state for this is kept in the database so there is no need to pass any images here
        This way it is easier to maintain at the expense of being slightly less efficient
        """

        if self.generate_thumbnails:
            self.update_thumbnails()

        if self.run_ai_models:
            # Run AI models on the images
            from eyened_orm.inference.inference import run_inference

            run_inference(self.session, device=None)

    def _import(self, data: List[PatientImport]):
        """
        Execute the entire import process with the provided data.

        Parameters:
        -----------
        data : List[PatientImport]
            List of PatientImport objects.

        Returns:
        --------
        List[ImageInstance]
            The image instances created during the import
        """

        self.init_objects(data)

        try:
            self.session.commit()

            # Write segmentation data
            for seg, data in self.pending_segmentation_writes:
                seg.write_data(data)

            if self.pending_segmentation_writes:
                self.session.commit()

        except Exception as e:
            self.session.rollback()
            raise RuntimeError(
                "Failed to commit the transaction. Nothing will be written to the database and no files have been created or changed"
            ) from e

        self.post_insert()
        # Save created images to return before clearing collections
        # return list(self.images)
        return [e for e in self._all_entities if isinstance(e, ImageInstance)]

    def _summary(self, data: List[PatientImport]) -> Dict:
        with self.session.begin_nested():
            self.init_objects(data)

            classes = {e.__class__ for e in self._all_entities}
            entities = {
                c: [e for e in self._all_entities if isinstance(e, c)] for c in classes
            }

            new_entities = {
                c: [item for item in items if item in self.created_entities]
                for c, items in entities.items()
            }

            # General statistics in dataframe-ready format
            general_stats = []
            for name, items in entities.items():
                total = len(items)
                new = len(new_entities[name])
                existing = total - new

                # Calculate percentages
                new_percentage = (new / total * 100) if total > 0 else 0
                existing_percentage = (existing / total * 100) if total > 0 else 0

                general_stats.append(
                    {
                        "Entity": name.__name__,
                        "Total": total,
                        "New": new,
                        "Existing": existing,
                        "New_Percentage": new_percentage,
                        "Existing_Percentage": existing_percentage,
                    }
                )

            # Column population statistics for new entities
            column_stats = {}
            for c, items in new_entities.items():
                if items:
                    column_stats[c] = self._get_populated_fields_stats(c, items)

            # Save project names before rolling back
            project_names = [
                project.ProjectName for project in entities.get(Project, [])
            ]

            # Complete summary
            summary = {
                "projects": project_names,
                "general_stats": general_stats,
                "column_stats": column_stats,
            }

            # Print summary as before
            print(f"\nImport Summary for Projects: {', '.join(summary['projects'])}")
            print("----------------  Object Statistics  ----------------")

            # Create and display dataframe directly from general_stats
            df_stats = pd.DataFrame(general_stats)
            # Format percentages for display
            df_stats["New_Percentage"] = df_stats["New_Percentage"].apply(
                lambda x: f"{x:.1f}%"
            )
            df_stats["Existing_Percentage"] = df_stats["Existing_Percentage"].apply(
                lambda x: f"{x:.1f}%"
            )
            print(df_stats.to_string(index=False))

            print("\n-----------  Column Population Statistics  -----------")
            print("- only for new entities")
            print("- values set to NULL are not considered populated")

            for c, stats in column_stats.items():
                if stats:
                    print(f"\nPopulated {c.__name__} Columns:")
                    df_columns = pd.DataFrame(stats)
                    # Format percentage for display
                    df_columns["Percentage"] = df_columns["Percentage"].apply(
                        lambda x: f"{x:.1f}%"
                    )
                    print(df_columns.to_string(index=False))

            if self.pending_segmentation_writes:
                print("\n-----------  Segmentation Consistency Checks  -----------")
                for i, (seg, data) in enumerate(self.pending_segmentation_writes):
                    try:
                        # Run ORM consistency check
                        seg.check_consistency()
                    except Exception as e:
                        print(f"ERROR: Segmentation {i} consistency check failed: {e}")

            # Rollback the nested transaction to avoid creating any objects
            # This happens automatically when exiting the with block

        return summary

    def import_many(
        self, data: List[PatientImport], summary: bool = False
    ) -> Union[List[ImageInstance], Dict]:
        """Import data or generate a summary of what would be imported."""
        try:
            if summary:
                return self._summary(data)
            else:
                return self._import(data)
        finally:
            # Always clear collections at the end to ensure stateless behavior
            self.created_entities = set()
            self.existing_entities = set()
            self.pending_segmentation_writes = []
            self.session.rollback()

    def import_one(
        self, data: Union[Dict, InstancePOSTFlat], summary: bool = False
    ) -> Union[List[ImageInstance], Dict]:
        """
        Import a single image using a simplified flat dictionary structure or InstancePOSTFlat object.
        """
        if isinstance(data, dict):
            data_obj = InstancePOSTFlat(**data)
        else:
            data_obj = data

        # Construct the hierarchical structure
        # 1. Extract ImageImport data (InstancePOST fields + image + attributes)
        exclude_fields = {
            "project_name",
            "patient_identifier",
            "sex",
            "birth_date",
            "study_date",
            "study_description",
            "series_id",
            "series_number",
            "series_instance_uid",
        }
        image_data = data_obj.model_dump(exclude=exclude_fields)
        image_item = ImageImport(**image_data)

        # 2. Create hierarchy
        series_item = SeriesImport(
            series_id=data_obj.series_id,
            series_number=data_obj.series_number,
            series_instance_uid=data_obj.series_instance_uid,
            images=[image_item],
        )

        study_item = StudyImport(
            study_date=data_obj.study_date,
            description=data_obj.study_description,
            series=[series_item],
        )

        patient_item = PatientImport(
            project_name=data_obj.project_name,
            patient_identifier=data_obj.patient_identifier,
            sex=data_obj.sex,
            birth_date=data_obj.birth_date,
            studies=[study_item],
        )

        # Call the appropriate method based on the summary flag
        return self.import_many([patient_item], summary=summary)

    def _get_populated_fields_stats(self, model_class, instances):
        """
        Return a dictionary of populated fields statistics for a list of model instances.

        Parameters:
        -----------
        model_class : SQLAlchemy model class
            The model class (Patient, Study, Series, ImageInstance) to analyze
        instances : List[model_class]
            List of model instances to analyze

        Returns:
        --------
        List[Dict]
            List of dictionaries with column stats, each with keys 'Column', 'Populated', 'Percentage'
        """
        if not instances:
            return []

        # Get all relevant columns from the model class
        from sqlalchemy import inspect as sa_inspect

        columns = [c.key for c in sa_inspect(model_class).mapper.column_attrs]

        # Count populated columns
        total_count = len(instances)
        column_stats = []

        for column in sorted(columns):
            # Skip primary keys and foreign keys
            if column.endswith("ID"):
                continue

            # Count non-None values
            populated_count = sum(
                1
                for instance in instances
                if getattr(instance, column, None) is not None
            )
            if populated_count == 0:
                continue

            percentage = (populated_count / total_count * 100) if total_count > 0 else 0

            column_stats.append(
                {
                    "Column": column,
                    "Populated": populated_count,
                    "Percentage": percentage,  # Return raw number for easy dataframe creation
                }
            )

        return column_stats

    def images(self) -> List[ImageInstance]:
        return [e for e in self._all_entities if isinstance(e, ImageInstance)]

    def update_thumbnails(self):
        """Update thumbnails for all images in the importer."""
        update_thumbnails(self.session, self.images)
