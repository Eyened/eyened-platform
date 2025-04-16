import datetime
import secrets
import shutil
import warnings
from pathlib import Path
from typing import Dict, List

import pandas as pd
from sqlalchemy import inspect

from eyened_orm import (
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
)
from eyened_orm.utils.config import get_config
from tqdm import tqdm


class Importer:
    def __init__(
        self,
        session,
        project_name: str,
        create_patients: bool = False,
        create_studies: bool = False,
        create_series: bool = True,
        run_ai_models: bool = True,
        generate_thumbnails: bool = True,
        copy_files: bool = False,
        env="test",
    ):
        """
        Initialize the Importer with database session and data to import.

        Parameters:
        -----------
        session : SQLAlchemy session
            Database session to use for the import
        project_name : str
            Name of the project to import data into
        create_studies : bool, default=False
            If True, create studies when they don't exist
        create_patients : bool, default=False
            If True, create patients when they don't exist
        create_series : bool, default=False
            If True, create series when they don't exist
        run_ai_models : bool, default=True
            If True, run AI models on the images after import
        generate_thumbnails : bool, default=True
            If True, generate thumbnails for the images after import
        copy_files : bool, default=False
            If True, copy image files to the images_basepath directory
        env : str, default="test"
            Environment to use for configuration (e.g., "test", "production").
        """
        self.session = session
        self.project_name = project_name

        self.create_patients = create_patients
        self.create_studies = create_studies
        self.create_series = create_series
        self.run_ai_models = run_ai_models
        self.generate_thumbnails = generate_thumbnails
        self.copy_files = copy_files
        self.config = get_config(env)
        self.copy_queue = []

        assert self.config['images_basepath'] is not None, "images_basepath must be set when using the importer"

        if self.copy_files:
            assert self.config['importer_copy_path'] is not None, "importer_copy_path must be set when copy_files is True"

            self.default_path_relative = Path(
                self.config["importer_default_path"]
            ).relative_to(self.config["images_basepath"])
        else:
            self.default_path_relative = None

    def init_objects(self, data: List[Dict]):
        """
        Traverses the data structure and creates patient, study and series objects.

        Creates the hierarchy from project down to series objects based on the data
        structure and configuration:
        - Patients are created if self.create_patients is True
        - Studies are created if self.create_studies is True
        - Series are created if self.create_series is True

        If objects don't exist in the database and cannot be created due to
        configuration settings, a RuntimeError is raised.

        Each created object is attached to its corresponding entry in the data structure.

        Parameters:
        ----------
        data : List[Dict]
            List of patient dictionaries with the following structure:
            [
                {
                    "patient_identifier": str,  # Optional patient identifier in the system
                    "props": {},                # Optional key-value properties for patient
                    "studies": [
                        {
                            "study_date": datetime.date,  # Optional study date
                            "props": {},                  # Optional key-value properties for study
                            "series": [
                                {
                                    "series_id": str,     # Optional series identifier
                                    "props": {},          # Optional key-value properties for series
                                    "images": [...]
                                }
                            ]
                        }
                    ]
                }
            ]

        Returns:
        --------
        Project
            The project object (either found or created)
        """
        self.project = None
        self.patients = []
        self.studies = []
        self.series = []
        self.images = []

        # Find or create project
        project = Project.by_name(self.session, self.project_name)
        if project is None:
            project = Project(ProjectName=self.project_name, External=True)
        self.project = project

        for patient_item in data:
            patient = self.find_or_create_patient(patient_item)
            self.patients.append(patient)

            for study_item in patient_item.get("studies", []):
                study = self.find_or_create_study(patient, study_item)
                self.studies.append(study)

                for series_item in study_item.get("series", []):
                    series = self.find_or_create_series(study, series_item)
                    self.series.append(series)

                    for image_item in series_item.get("images", []):
                        image = self.find_or_create_image(series, image_item)
                        self.images.append(image)

    def find_or_create_image(self, series, image_data):
        props = image_data.get("props", {})
        im = ImageInstance(**props)
        im.Series = series

        # Set other required attributes
        # TODO: remove once we remove them from the DB
        im.SourceInfoID = 37
        im.ModalityID = 14
        im.DatasetIdentifier = self.get_image_path(image_data)
        image_data["instance"] = im
        return im

    def find_or_create_series(self, study, series_item):
        series_id = series_item.get("series_id")
        props = series_item.get("props", {})
        series = None

        string_repr = f"Series with identifier '{series_id}' for patient '{study.Patient.PatientIdentifier}', study '{study.StudyDate}'"
        # Try to find existing series
        if series_id is not None:
            series = study.get_series_by_id(self.session, series_id)
            if series is None:
                warnings.warn(f"{string_repr} not found.")

        if series is None:
            if not self.create_series:
                raise RuntimeError(
                    f"{string_repr} not found and create_series=False")

            # Create new series
            series = Series(**props)
            series.Study = study
        elif props:
            warnings.warn(
                f"Props provided for existing series ({string_repr}) "
                f"will be ignored. The importer does not update existing series."
            )

        # Store the series object in the data structure
        return series

    def find_or_create_study(self, patient, study_item):
        study_date = study_item.get("study_date", self.config["default_date"])
        props = study_item.get("props", {})

        if not isinstance(study_date, datetime.date):
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
            study = Study(StudyDate=study_date, **props)
            study.Patient = patient
        elif props:
            warnings.warn(
                f"Props provided for existing study (date: '{study_date}', patient: '{patient.PatientIdentifier}') "
                f"will be ignored. The importer does not update existing studies."
            )

        return study

    def find_or_create_patient(self, patient_item):
        patient_identifier = patient_item.get("patient_identifier")
        patient_props = patient_item.get("props", {})

        # Try to find existing patient
        patient = self.project.get_patient_by_identifier(
            self.session, patient_identifier)

        if patient is None:
            if not self.create_patients:
                raise RuntimeError(
                    f"Patient with identifier '{patient_identifier}' not found and create_patients=False"
                )

            # Create new patient
            patient = Patient(**patient_props)
            patient.Project = self.project
            patient.PatientIdentifier = (
                patient_identifier
                if patient_identifier is not None
                # default patient identifier is random
                else secrets.token_hex(8)
            )
        elif patient_props:
            warnings.warn(
                f"Props provided for existing patient '{patient_identifier}' will be ignored. "
                f"The importer does not update existing patients."
            )

        return patient

    def get_image_path(self, image_data):
        """
        Checks if the image path is absolute and within the images_basepath directory.
        If copy_files is True, it generates a unique filename for the copied file.
        The generated filenames are stored in the copy_queue for later copying.
        """
        basepath = Path(self.config["images_basepath"])

        path_or_url = image_data.get("image")
        if path_or_url.startswith("http"):
            raise NotImplementedError()

        fpath = Path(path_or_url)
        assert fpath.exists(), f"File does not exist: {fpath}"
        assert fpath.is_absolute(), f"Path must be absolute: {fpath}"

        if self.copy_files:
            # Generate a unique filename for the copied file
            unique_id = secrets.token_hex(16)
            extension = fpath.suffix  # Preserve the original extension
            target = str(self.default_path_relative /
                         f"{unique_id}{extension}")
            self.copy_queue.append((fpath, target))
            return target
        else:
            # Verify path is within the images_basepath
            try:
                return str(fpath.relative_to(basepath))
            except ValueError:
                raise ValueError(
                    f"File path {fpath} is not within the images_basepath directory "
                    f"({basepath}). Verify that the images_basepath is set correctly."
                )

    def copy_images(self):
        """
        Copies image files from their original locations to the images_basepath directory.

        This should be called after init_objects()
        """
        if not self.copy_files:
            return

        failed_copies = []
        for source_path, dest_path in tqdm(self.copy_queue, desc="Copying files", unit="file"):
            try:
                # Ensure the destination directory exists
                dest_dir = Path(dest_path).parent
                dest_dir.mkdir(parents=True, exist_ok=True)

                shutil.copy2(source_path, dest_path)
            except Exception as e:
                failed_copies.append((source_path, dest_path))

        # Clear the copy queue
        self.copy_queue = []

        if failed_copies:
            warnings.warn(f"Failed to copy {len(failed_copies)} files:")
            for source_path, dest_path in failed_copies:
                warnings.warn(f"  - {source_path} -> {dest_path}")

    def post_insert(self):
        """
        Here we run preprocessing, AI models and generate thumbnails
        The state for this is kept in the database so there is no need to pass any images here
        This way it is easier to maintain at the expense of being slightly less efficient
        """
        if self.run_ai_models:
            # Run AI models on the images
            from eyened_orm.inference.inference import run_inference

            run_inference(self.session, self.config, device=None)
        if self.generate_thumbnails:
            # Generate thumbnails for the images
            from eyened_orm.importer.thumbnails import update_thumbnails

            update_thumbnails(
                self.session,
                self.config,
            )

    def exec(self, data: List[Dict]):
        """
        Execute the entire import process with the provided data.

        Parameters:
        -----------
        data : List[Dict]
            List of patient dictionaries with the following structure:
            [
                {
                    "patient_id": str,  # Patient identifier in the system
                    "props": {},        # Optional key-value properties for patient
                    "studies": [
                        {
                            "study_date": str,
                            "props": {},  # Optional key-value properties for study
                            "series": [
                                {
                                    "series_id": str,
                                    "props": {},  # Optional key-value properties for series
                                    "images": [
                                        {
                                            "image": str,  # Path to image
                                            "props": {},   # Optional key-value properties for image
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]

        Returns:
        --------
        Project
            The project object associated with the import
        """

        # Create a deep copy of the data to avoid modifying the user's original data
        # data = copy.deepcopy(data)

        # Initialize progress tracking
        steps = ['Creating hierarchy',
                 'Database commit', 'Post-processing']
        if self.copy_files:
            steps.insert(1, 'Copying files')

        # Create a progress bar for overall process
        with tqdm(total=len(steps), desc="Import Progress") as pbar:
            # Create the hierarchy of objects
            pbar.set_description(
                "Creating patients, studies, series, instances")
            self.init_objects(data)
            pbar.update(1)

            # Copy files if needed (before committing to ensure all files are copied)
            if self.copy_files:
                pbar.set_description("Copying image files")
                self.copy_images()
                pbar.update(1)

            # Commit to database
            pbar.set_description("Committing to database")
            self.session.add(self.project)

            # Add all created / updated objects to the session
            for item in [*self.patients, *self.studies, *self.series, *self.images]:
                self.session.add(item)

            try:
                self.session.commit()
                pbar.write("Successfully committed to database")
                pbar.update(1)
            except Exception as e:
                pbar.write("Failed to commit to database")
                self.session.rollback()
                # TODO: roll back copied files
                raise RuntimeError(
                    "Failed to commit the transaction. Nothing will be written to the database and no files have been created or changed"
                ) from e

            # Process the imported data (run AI models, generate thumbnails)
            pbar.set_description("Running post-processing")
            self.post_insert()
            pbar.update(1)

    def summary(self, data: List[Dict]) -> Dict:

        with self.session.begin_nested():
            self.init_objects(data)
            
            class_map = {
                'patients': Patient,
                'studies': Study,
                'series': Series,
                'images': ImageInstance
            }
            entities = {k: getattr(self, k) for k in class_map.keys()}
            new_entities = {
                name: [item for item in items if not inspect(item).persistent]
                for name, items in entities.items()
            }

            summary = {
                "project": self.project_name,
                **{
                    name: {
                        "total": len(items),
                        "new": len(new_entities[name]),
                        "existing": len(items) - len(new_entities[name])
                    }
                    for name, items in entities.items()
                }
            }

            print(f"\nImport Summary for Project: {summary['project']}")
            print('----------------  Object Statistics  ----------------')

            df_stats = pd.DataFrame({
                'Entity': [name.capitalize() for name in entities.keys()],
                'Total': [len(entity_attr) for entity_attr in entities.values()],
                'New': [len(new_entities[name]) for name in entities.keys()],
                'Existing': [
                    len(entity_attr) - len(new_entities[name])
                    for name, entity_attr in entities.items()
                ]
            })
            print(df_stats.to_string(index=False))

            print('\n-----------  Column Population Statistics  -----------')
            print('- only for new entities')
            print('- values set to NULL are not considered populated')

            for name, items in new_entities.items():
                if items:
                    print(f"\nPopulated {name.capitalize()} Columns:")
                    self._display_populated_fields_summary(
                        class_map[name], items)

            # Rollback the nested transaction to avoid creating any objects
            # This happens automatically when exiting the with block
        return summary

    def _display_populated_fields_summary(self, model_class, instances):
        """
        Display a summary of populated fields for a list of model instances.

        Parameters:
        -----------
        model_class : SQLAlchemy model class
            The model class (Patient, Study, Series, ImageInstance) to analyze
        instances : List[model_class]
            List of model instances to analyze
        """

        if not instances:
            print("No instances to analyze")
            return

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

            percentage = (
                (populated_count / total_count * 100) if total_count > 0 else 0
            )

            column_stats.append({
                'Column': column,
                'Populated': populated_count,
                'Percentage': f"{percentage:.1f}%"
            })

        if column_stats:
            df_columns = pd.DataFrame(column_stats)
            print(df_columns.to_string(index=False))
        else:
            print("No populated columns found")
