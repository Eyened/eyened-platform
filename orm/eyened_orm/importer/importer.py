import datetime
import secrets
import warnings
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
import pandas as pd
from sqlalchemy import inspect, select

from eyened_orm import (
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
)
from eyened_orm.attributes import AttributeDataType, AttributeDefinition, AttributeValue

from eyened_orm.image_instance import (
    DeviceInstance,
    DeviceModel,
    Modality,
    Scan,
    SourceInfo,
)
from eyened_orm.importer.thumbnails import update_thumbnails
from eyened_orm.project import ExternalEnum
from eyened_orm.segmentation import Datatype, Segmentation

# TODO: fix this!
# from eyened_orm.utils.config import EyenedORMConfig

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
        run_ai_models: bool = False,
        generate_thumbnails: bool = True,
    ):
        """
        Initialize the Importer with database session and data to import.

        Parameters:
        -----------
        session : SQLAlchemy session
            Database session to use for the import
        config : ORMSettings
            Configuration to use for the import
        create_patients : bool, default=False
            If True, create patients when they don't exist
        create_studies : bool, default=False
            If True, create studies when they don't exist
        create_series : bool, default=False
            If True, create series when they don't exist
        create_projects : bool, default=False
            If True, create project when it doesn't exist
        run_ai_models : bool, default=False
            If True, run AI models on the images after import
        generate_thumbnails : bool, default=True
            If True, generate thumbnails for the images after import

        """
        self.session = session
        self.config = None
        self.create_patients = create_patients
        self.create_studies = create_studies
        self.create_series = create_series
        self.create_projects = create_projects
        self.run_ai_models = run_ai_models
        self.generate_thumbnails = generate_thumbnails

        assert (
            self.config.images_basepath is not None
        ), "images_basepath must be set when using the importer"

        # Initialize empty collections
        self._clear_collections()

    def _clear_collections(self):
        """
        Clear all collection attributes to reset state.
        """
        self.projects = []
        self.patients = []
        self.studies = []
        self.series = []
        self.images = []
        self.attribute_definitions = {}
        self.attribute_values = []
        self.segmentations = []
        self.pending_segmentation_writes = []
        self.device_models = []
        self.device_instances = []
        self.scans = []

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
        self._clear_collections()

        # Process each patient
        for patient_item in data:
            # Get or create the project for this patient
            project = self.get_or_create_project(patient_item.project_name)

            patient = self.find_or_create_patient(patient_item, project)
            self.patients.append(patient)

            for study_item in patient_item.studies:
                study = self.find_or_create_study(patient, study_item)
                self.studies.append(study)

                for series_item in study_item.series:
                    series = self.find_or_create_series(study, series_item)
                    self.series.append(series)

                    for image_item in series_item.images:
                        image = self.find_or_create_image(series, image_item)
                        self.images.append(image)

                        if image_item.attributes:
                            self._process_attributes(image, image_item.attributes)

                        if image_item.segmentations:
                            self._process_segmentations(image, image_item.segmentations)

        return self.projects

    def _process_attributes(self, image: ImageInstance, attributes_data: Dict):
        for name, value in attributes_data.items():
            if name in self.attribute_definitions:
                attr_def = self.attribute_definitions[name]
            else:
                stmt = select(AttributeDefinition).where(
                    AttributeDefinition.AttributeName == name
                )
                result = self.session.execute(stmt).scalars().first()
                if result:
                    attr_def = result
                else:
                    if isinstance(value, float):
                        dtype = AttributeDataType.Float
                    elif isinstance(value, int):
                        dtype = AttributeDataType.Int
                    elif isinstance(value, (dict, list)):
                        dtype = AttributeDataType.JSON
                    else:
                        dtype = AttributeDataType.String

                    attr_def = AttributeDefinition(
                        AttributeName=name, AttributeDataType=dtype
                    )
                self.attribute_definitions[name] = attr_def

            val_kwargs = {}
            if attr_def.AttributeDataType == AttributeDataType.Float:
                val_kwargs["ValueFloat"] = float(value)
            elif attr_def.AttributeDataType == AttributeDataType.Int:
                val_kwargs["ValueInt"] = int(value)
            elif attr_def.AttributeDataType == AttributeDataType.String:
                val_kwargs["ValueText"] = str(value)
            elif attr_def.AttributeDataType == AttributeDataType.JSON:
                val_kwargs["ValueJSON"] = value

            attr_val = AttributeValue(
                AttributeDefinition=attr_def, ImageInstance=image, **val_kwargs
            )
            self.attribute_values.append(attr_val)

    def _process_segmentations(
        self, image: ImageInstance, segmentations_data: List[SegmentationImport]
    ):
        from eyened_orm import Creator, Feature

        for item in segmentations_data:
            data = item.data

            seg = Segmentation(
                DataType=item.data_type,
                DataRepresentation=item.data_representation,
                Depth=item.depth,
                Height=item.height,
                Width=item.width,
                SparseAxis=item.sparse_axis,
                ImageProjectionMatrix=item.image_projection_matrix,
                ScanIndices=item.scan_indices,
                Threshold=item.threshold,
                ReferenceSegmentationID=item.reference_segmentation_id,
                ImageInstance=image,
            )

            # Set metadata if provided
            if item.creator_name:
                creator = Creator.by_name(self.session, item.creator_name)
                if creator is None:
                    raise ValueError(
                        f"Creator '{item.creator_name}' not found in database"
                    )
                seg.CreatorID = creator.CreatorID

            if item.feature_name:
                feature = Feature.by_name(self.session, item.feature_name)
                if feature is None:
                    raise ValueError(
                        f"Feature '{item.feature_name}' not found in database"
                    )
                seg.FeatureID = feature.FeatureID

            # Infer DataType if missing
            if seg.DataType is None:
                if data.dtype == np.uint8:
                    seg.DataType = Datatype.R8
                elif data.dtype == np.uint16:
                    seg.DataType = Datatype.R16UI
                elif data.dtype == np.uint32:
                    seg.DataType = Datatype.R32UI
                elif data.dtype == np.float32:
                    seg.DataType = Datatype.R32F
                else:
                    seg.DataType = Datatype.R8

            # Set dims from image if missing
            if seg.Width is None:
                seg.Width = image.Columns_x
            if seg.Height is None:
                seg.Height = image.Rows_y
            if seg.Depth is None:
                seg.Depth = image.NrOfFrames if image.NrOfFrames else 1

            self.segmentations.append(seg)
            self.pending_segmentation_writes.append((seg, data))

    def get_or_create_project(self, project_name: str) -> Project:
        # Check if we've already processed this project
        for p in self.projects:
            if p.ProjectName == project_name:
                return p

        # Try to find the project in the database
        project = Project.by_name(self.session, project_name)

        # Create the project if it doesn't exist and we're allowed to
        if project is None:
            if not self.create_projects:
                raise RuntimeError(
                    f"Project with name '{project_name}' not found and create_projects=False"
                )
            project = Project(ProjectName=project_name, External=ExternalEnum.Y)

        self.projects.append(project)
        return project

    def find_or_create_patient(
        self, patient_item: PatientImport, project: Project
    ) -> Patient:
        patient_identifier = patient_item.patient_identifier

        # Try to find existing patient
        patient = project.get_patient_by_identifier(self.session, patient_identifier)

        if patient is None:
            if not self.create_patients:
                raise RuntimeError(
                    f"Patient with identifier '{patient_identifier}' not found and create_patients=False"
                )

            # Create new patient
            patient = Patient(
                Sex=patient_item.sex,
                BirthDate=patient_item.birth_date,
                Project=project,
                PatientIdentifier=(
                    patient_identifier
                    if patient_identifier is not None
                    # default patient identifier is random
                    else secrets.token_hex(8)
                ),
            )
        # We don't warn about ignored props anymore as requested/implied by simplified logic,
        # but could add back if needed. The original warned if props were present.
        elif patient_item.sex is not None or patient_item.birth_date is not None:
            warnings.warn(
                f"Properties provided for existing patient '{patient_identifier}' will be ignored. "
                f"The importer does not update existing patients."
            )

        return patient

    def find_or_create_device_instance(
        self,
        device_id: Union[int, None],
        manufacturer: Union[str, None],
        model: Union[str, None],
        serial_number: Union[str, None],
        description: Union[str, None],
    ) -> DeviceInstance:
        # 1. Try to find by ID if provided
        if device_id is not None:
            # Check cache
            for dev in self.device_instances:
                if dev.DeviceInstanceID == device_id:
                    return dev

            # Check DB
            device_instance = self.session.get(DeviceInstance, device_id)
            if device_instance:
                self.device_instances.append(device_instance)
                return device_instance
            warnings.warn(
                f"DeviceInstance with ID {device_id} not found. Falling back to attributes."
            )

        # 2. Find or create by attributes
        manufacturer = manufacturer or "Unknown"
        model = model or "Unknown"
        description = description or "Unknown"

        # Find/Create DeviceModel
        device_model = None
        # Check cache
        for dm in self.device_models:
            if dm.Manufacturer == manufacturer and dm.ManufacturerModelName == model:
                device_model = dm
                break

        if device_model is None:
            device_model = DeviceModel.by_manufacturer(
                manufacturer, model, self.session
            )

        if device_model is None:
            device_model = DeviceModel(
                Manufacturer=manufacturer, ManufacturerModelName=model
            )

        if device_model not in self.device_models:
            self.device_models.append(device_model)

        # Find/Create DeviceInstance
        device_instance = None
        # Check cache
        for di in self.device_instances:
            # We need to check if it matches. If it's a new object, DeviceModel might be object comparison.
            # If existing, we might check IDs.
            # Simplify: check description and model match

            # If di has DeviceModel object
            di_model = di.DeviceModel
            if di_model is None and di.DeviceModelID is not None:
                # Just in case logic, though normally we'd have object or ID
                if (
                    device_model.DeviceModelID == di.DeviceModelID
                    and di.Description == description
                ):
                    device_instance = di
                    break
            elif di_model is not None:
                if di_model == device_model and di.Description == description:
                    device_instance = di
                    break

        if device_instance is None:
            # Check DB
            # We need DeviceModelID for query. If device_model is new, we can't query by ID reliably unless we flush.
            # But we avoid flush here.
            # If device_model is new (no ID), then device_instance MUST be new (or at least not in DB with that model).

            is_model_persistent = (
                inspect(device_model).persistent or inspect(device_model).detached
            )
            if is_model_persistent:
                stmt = select(DeviceInstance).where(
                    DeviceInstance.DeviceModelID == device_model.DeviceModelID,
                    DeviceInstance.Description == description,
                )
                device_instance = self.session.scalar(stmt)

            if device_instance is None:
                device_instance = DeviceInstance(
                    DeviceModel=device_model,
                    Description=description,
                    SerialNumber=serial_number,
                )

        if device_instance not in self.device_instances:
            self.device_instances.append(device_instance)

        return device_instance

    def find_or_create_scan(self, scan_mode: str) -> Scan:
        # Check cache
        for s in self.scans:
            if s.ScanMode == scan_mode:
                return s

        # Check DB
        scan = self.session.execute(
            select(Scan).where(Scan.ScanMode == scan_mode)
        ).scalar_one_or_none()

        if scan is None:
            scan = Scan(ScanMode=scan_mode)

        if scan not in self.scans:
            self.scans.append(scan)

        return scan

    def find_or_create_image(
        self, series: Series, image_data: ImageImport
    ) -> ImageInstance:
        device_instance = self.find_or_create_device_instance(
            device_id=image_data.device_id,
            manufacturer=image_data.device_manufacturer,
            model=image_data.device_model,
            serial_number=image_data.device_serial_number,
            description=image_data.device_description,
        )

        modality = image_data.modality
        if isinstance(modality, str):
            # Try to map string to Modality enum
            try:
                modality = Modality(modality)
            except ValueError:
                # Remove spaces and try case-insensitive matching if needed,
                # but for now let's try direct mapping or matching name
                found = False
                for m in Modality:
                    if m.value == modality or m.name == modality:
                        modality = m
                        found = True
                        break

                if not found:
                    # Try mapping "Color Fundus" -> ColorFundus
                    sanitized = modality.replace(" ", "")
                    for m in Modality:
                        if m.name.lower() == sanitized.lower():
                            modality = m
                            found = True
                            break

                if not found:
                    warnings.warn(
                        f"Could not map string '{image_data.modality}' to Modality enum. Leaving as None."
                    )
                    modality = None

        scan = None
        if image_data.scan_mode:
            scan = self.find_or_create_scan(image_data.scan_mode)

        if image_data.source_info_id:
            source_info_id = image_data.source_info_id
            # We assume ID is valid or will be checked by foreign key constraint,
            # but we need to assign it. ImageInstance takes SourceInfo object or ID.
            # Ideally we fetch the object to be safe/consistent, or we can just set the ID on the object if we change ImageInstance constructor call.
            # However, ImageInstance expects an object for relationships usually if we want backrefs to work immediately in memory.
            # Let's try to fetch it to be safe.
            source_info = self.session.get(SourceInfo, source_info_id)
            if not source_info:
                raise ValueError(f"SourceInfo with ID {source_info_id} not found")
        else:
            source_info = SourceInfo.by_name(self.session, "MISC")

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
            DatasetIdentifier=self.get_image_path(image_data),
            Series=series,
            SourceInfo=source_info,
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

        return im

    def find_or_create_series(self, study: Study, series_item: SeriesImport) -> Series:
        series_id = series_item.series_id
        series = None

        string_repr = f"Series with identifier '{series_id}' for patient '{study.Patient.PatientIdentifier}', study '{study.StudyDate}'"
        # Try to find existing series
        if series_id is not None:
            series = study.get_series_by_id(self.session, series_id)
            if series is None:
                warnings.warn(f"{string_repr} not found.")

        if series is None:
            if not self.create_series:
                raise RuntimeError(f"{string_repr} not found and create_series=False")

            # Create new series
            series = Series(
                SeriesNumber=series_item.series_number,
                SeriesInstanceUid=series_item.series_instance_uid,
                Study=study,
            )
        elif (
            series_item.series_number is not None
            or series_item.series_instance_uid is not None
        ):
            warnings.warn(
                f"Properties provided for existing series ({string_repr}) "
                f"will be ignored. The importer does not update existing series."
            )

        return series

    def find_or_create_study(self, patient: Patient, study_item: StudyImport) -> Study:
        default_study_date = self.config.default_study_date

        study_date = study_item.study_date or default_study_date

        # Convert string date to datetime.date if necessary
        if isinstance(study_date, str):
            # Should be handled by Pydantic, but if default_study_date from config is str...
            # The DTO enforces date for study_item.study_date.
            try:
                year, month, day = map(int, study_date.split("-"))
                study_date = datetime.date(year, month, day)
            except ValueError:
                raise ValueError(f"Invalid study date format: {study_date}")

        if not isinstance(study_date, datetime.date):
            # Could happen if config is wrong
            raise ValueError(
                f"Study date must be a datetime.date object for patient '{patient.PatientIdentifier}'"
            )

        study = patient.get_study_by_date(study_date)

        if study is None:
            if not self.create_studies:
                raise RuntimeError(
                    f"Study with date '{study_date}' for patient '{patient.PatientIdentifier}' not found and create_studies=False"
                )

            # Create new study
            study = Study(
                StudyDate=study_date,
                StudyDescription=study_item.description,
                Patient=patient,
            )
        elif study_item.description is not None:
            warnings.warn(
                f"Properties provided for existing study (date: '{study_date}', patient: '{patient.PatientIdentifier}') "
                f"will be ignored. The importer does not update existing studies."
            )

        return study

    def get_image_path(self, image_data: ImageImport) -> str:
        """
        Checks if the image path:
         - is absolute and within the images_basepath directory
         - is relative and exists within the images_basepath directory
        """
        basepath = self.config.images_basepath

        path_or_url = image_data.image
        if path_or_url.startswith("http"):
            raise NotImplementedError()

        fpath = Path(path_or_url)

        if fpath.is_absolute():
            assert fpath.is_relative_to(
                basepath
            ), f"File path {fpath} is absolute is not within the images_basepath directory {basepath}"
        else:
            # relative path provided, make it absolute and check
            fpath = Path(basepath) / fpath
            assert fpath.exists(), f"File does not exist: {fpath}"

        return str(fpath.relative_to(basepath))

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

        # Add attributes definitions that are new
        for attr_def in self.attribute_definitions.values():
            if not inspect(attr_def).persistent:
                self.session.add(attr_def)

        # Add all created / updated objects to the session
        for item in [
            *self.projects,
            *self.patients,
            *self.studies,
            *self.series,
            *self.images,
            *self.attribute_values,
            *self.segmentations,
            *self.device_models,
            *self.device_instances,
            *self.scans,
        ]:
            self.session.add(item)

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
        return list(self.images)

    def _summary(self, data: List[PatientImport]) -> Dict:
        with self.session.begin_nested():
            self.init_objects(data)

            class_map = {
                "patients": Patient,
                "studies": Study,
                "series": Series,
                "images": ImageInstance,
                "attribute_definitions": AttributeDefinition,
                "attribute_values": AttributeValue,
                "segmentations": Segmentation,
                "device_models": DeviceModel,
                "device_instances": DeviceInstance,
                "scans": Scan,
            }
            entities = {}
            entities["patients"] = self.patients
            entities["studies"] = self.studies
            entities["series"] = self.series
            entities["images"] = self.images
            entities["attribute_definitions"] = list(
                self.attribute_definitions.values()
            )
            entities["attribute_values"] = self.attribute_values
            entities["segmentations"] = self.segmentations
            entities["device_models"] = self.device_models
            entities["device_instances"] = self.device_instances
            entities["scans"] = self.scans

            new_entities = {
                name: [item for item in items if not inspect(item).persistent]
                for name, items in entities.items()
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
                        "Entity": name.capitalize(),
                        "Total": total,
                        "New": new,
                        "Existing": existing,
                        "New_Percentage": new_percentage,
                        "Existing_Percentage": existing_percentage,
                    }
                )

            # Column population statistics for new entities
            column_stats = {}
            for name, items in new_entities.items():
                if items:
                    column_stats[name] = self._get_populated_fields_stats(
                        class_map[name], items
                    )

            # Save project names before rolling back
            project_names = [project.ProjectName for project in self.projects]

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

            for name, stats in column_stats.items():
                if stats:
                    print(f"\nPopulated {name.capitalize()} Columns:")
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
            self._clear_collections()

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

    def update_thumbnails(self):
        """Update thumbnails for all images in the importer."""
        update_thumbnails(self.session, self.images)
