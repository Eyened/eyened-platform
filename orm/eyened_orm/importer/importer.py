import datetime
import secrets
import shutil
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd
from sqlalchemy import inspect

from eyened_orm import (
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
)
from eyened_orm.utils.config import EyenedORMConfig, get_config
from tqdm import tqdm


class Importer:
    def __init__(
        self,
        session,
        create_patients: bool = False,
        create_studies: bool = False,
        create_series: bool = True,
        create_project: bool = False,
        run_ai_models: bool = True,
        generate_thumbnails: bool = True,
        copy_files: bool = False,
        config: str | EyenedORMConfig = "test",
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
        create_project : bool, default=False
            If True, create project when it doesn't exist
        run_ai_models : bool, default=True
            If True, run AI models on the images after import
        generate_thumbnails : bool, default=True
            If True, generate thumbnails for the images after import
        copy_files : bool, default=False
            If True, copy image files to the images_basepath directory
        config : str, default="test"
            config object (see config.sample.py) or environment to load for configuration (e.g., "test", "production").
        """
        self.session = session

        self.create_patients = create_patients
        self.create_studies = create_studies
        self.create_series = create_series
        self.create_project = create_project
        self.run_ai_models = run_ai_models
        self.generate_thumbnails = generate_thumbnails
        self.copy_files = copy_files
        if isinstance(config, str):
            self.config = get_config(config)
        elif isinstance(config, EyenedORMConfig):
            self.config = config
        else:
            raise ValueError(f"Invalid config type: {type(config)}")
        self.copy_queue = []

        assert self.config.images_basepath is not None, "images_basepath must be set when using the importer"

        if self.copy_files:
            assert self.config.importer_copy_path is not None, "importer_copy_path must be set when copy_files is True"

            self.default_path_relative = Path(
                self.config.importer_copy_path
            ).relative_to(self.config.images_basepath)
        else:
            self.default_path_relative = None
        self.images_basepath_local = self.config.images_basepath_local
        
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
        self.copy_queue = []

    def init_objects(self, data: List[Dict]):
        """
        Traverses the data structure and creates patient, study and series objects.

        Creates the hierarchy from project down to series objects based on the data
        structure and configuration:
        - Project is created if self.create_project is True
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
                    "project_name": str,            # Required project name
                    "patient_identifier": str,      # Optional patient identifier in the system
                    "props": {},                    # Optional key-value properties for patient
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
        List[Project]
            The project objects (either found or created)
        """
        # Clear collections before starting
        self._clear_collections()
        
        # Check that all patient items have a project_name
        for i, patient_item in enumerate(data):
            if "project_name" not in patient_item or not patient_item["project_name"]:
                raise ValueError(f"project_name is required for patient at index {i}")

        # Process each patient
        for patient_item in data:
            # Find or create the project for this patient
            project = self.find_or_create_project(patient_item["project_name"])
            self.projects.append(project)
            
            patient = self.find_or_create_patient(patient_item, project)
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
                        
        return self.projects

    def find_or_create_project(self, project_name: str) -> Project:
        # Check if we've already processed this project
        for project in self.projects:
            if project.ProjectName == project_name:
                return project
                
        # Try to find the project in the database
        project = Project.by_name(self.session, project_name)
        
        # Create the project if it doesn't exist and we're allowed to
        if project is None:
            if not self.create_project:
                raise RuntimeError(
                    f"Project with name '{project_name}' not found and create_project=False"
                )
            project = Project(ProjectName=project_name, External=True)
            
        # Add to our list of projects
        
        return project
    
    def find_or_create_patient(self, patient_item, project):
        patient_identifier = patient_item.get("patient_identifier")
        patient_props = patient_item.get("props", {})

        # Try to find existing patient
        patient = project.get_patient_by_identifier(
            self.session, patient_identifier)

        if patient is None:
            if not self.create_patients:
                raise RuntimeError(
                    f"Patient with identifier '{patient_identifier}' not found and create_patients=False"
                )

            # Create new patient
            patient = Patient(**patient_props)
            patient.Project = project
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
        default_study_date = self.config.default_study_date or datetime.date(1970,1,1)
        props = study_item.get("props", {})

        # Convert string date to datetime.date if necessary
        if isinstance(default_study_date, str):
            try:
                # Assuming format is 'yyyy-mm-dd'
                year, month, day = map(int, default_study_date.split('-'))
                default_study_date = datetime.date(year, month, day)
            except ValueError:
                raise ValueError(
                    f"Invalid study date format: '{default_study_date}'. Expected format: 'yyyy-mm-dd' for patient '{patient.PatientIdentifier}'"
                )

        if not isinstance(default_study_date, datetime.date):
            raise ValueError(
                f"Study date must be a datetime.date object for patient '{patient.PatientIdentifier}'"
            )

        study = patient.get_study_by_date(default_study_date)

        if study is None:
            if not self.create_studies:
                raise RuntimeError(
                    f"Study with date '{default_study_date}' for patient '{patient.PatientIdentifier}' not found and create_studies=False"
                )

            # Create new study
            study = Study(StudyDate=default_study_date, **props)
            study.Patient = patient
        elif props:
            warnings.warn(
                f"Props provided for existing study (date: '{default_study_date}', patient: '{patient.PatientIdentifier}') "
                f"will be ignored. The importer does not update existing studies."
            )

        return study

    

    def get_image_path(self, image_data):
        """
        Checks if the image path is absolute and within the images_basepath directory.
        If copy_files is True, it generates a unique filename for the copied file.
        The generated filenames are stored in the copy_queue for later copying.
        """
        basepath = Path(self.config.images_basepath)

        path_or_url = image_data.get("image")
        if path_or_url.startswith("http"):
            raise NotImplementedError()

        fpath = Path(path_or_url)

        local_path = Path(self.images_basepath_local) / fpath.relative_to(basepath) if self.images_basepath_local else fpath
        
        assert local_path.exists(), f"File does not exist: {local_path}"
        assert local_path.is_absolute(), f"Path must be absolute: {local_path}"

        if self.copy_files:
            # Generate a unique filename for the copied file
            unique_id = secrets.token_hex(16)
            extension = fpath.suffix  # Preserve the original extension
            target = str(self.default_path_relative /
                         f"{unique_id}{extension}")
            self.copy_queue.append((local_path, target))
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

    def _import(self, data: List[Dict]):
        """
        Execute the entire import process with the provided data.

        Parameters:
        -----------
        data : List[Dict]
            List of patient dictionaries with the following structure:
            [
                {
                    "project_name": str,           # Required project name
                    "patient_identifier": str,     # Optional patient identifier in the system
                    "props": {},                   # Optional key-value properties for patient
                    "studies": [
                        {
                            "study_date": str,
                            "props": {},           # Optional key-value properties for study
                            "series": [
                                {
                                    "series_id": str,
                                    "props": {},   # Optional key-value properties for series
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
        List[ImageInstance]
            The image instances created during the import
        """

        self.init_objects(data)
        # Add all created / updated objects to the session
        for item in [*self.projects, *self.patients, *self.studies, *self.series, *self.images]:
            self.session.add(item)

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(
                "Failed to commit the transaction. Nothing will be written to the database and no files have been created or changed"
            ) from e

        self.post_insert()
        # Save created images to return before clearing collections
        return list(self.images)
    
    def _summary(self, data: List[Dict]) -> Dict:
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

            # General statistics in dataframe-ready format
            general_stats = []
            for name, items in entities.items():
                total = len(items)
                new = len(new_entities[name])
                existing = total - new
                
                # Calculate percentages
                new_percentage = (new / total * 100) if total > 0 else 0
                existing_percentage = (existing / total * 100) if total > 0 else 0
                
                general_stats.append({
                    'Entity': name.capitalize(),
                    'Total': total,
                    'New': new,
                    'Existing': existing,
                    'New_Percentage': new_percentage,
                    'Existing_Percentage': existing_percentage
                })
            
            # Column population statistics for new entities
            column_stats = {}
            for name, items in new_entities.items():
                if items:
                    column_stats[name] = self._get_populated_fields_stats(
                        class_map[name], items)

            # Save project names before rolling back
            project_names = [project.ProjectName for project in self.projects]
            
            # Complete summary
            summary = {
                "projects": project_names,
                "general_stats": general_stats,
                "column_stats": column_stats
            }

            # Print summary as before
            print(f"\nImport Summary for Projects: {', '.join(summary['projects'])}")
            print('----------------  Object Statistics  ----------------')

            # Create and display dataframe directly from general_stats
            df_stats = pd.DataFrame(general_stats)
            # Format percentages for display
            df_stats['New_Percentage'] = df_stats['New_Percentage'].apply(lambda x: f"{x:.1f}%")
            df_stats['Existing_Percentage'] = df_stats['Existing_Percentage'].apply(lambda x: f"{x:.1f}%")
            print(df_stats.to_string(index=False))

            print('\n-----------  Column Population Statistics  -----------')
            print('- only for new entities')
            print('- values set to NULL are not considered populated')

            for name, stats in column_stats.items():
                if stats:
                    print(f"\nPopulated {name.capitalize()} Columns:")
                    df_columns = pd.DataFrame(stats)
                    # Format percentage for display
                    df_columns['Percentage'] = df_columns['Percentage'].apply(lambda x: f"{x:.1f}%")
                    print(df_columns.to_string(index=False))

            # Rollback the nested transaction to avoid creating any objects
            # This happens automatically when exiting the with block
        
        return summary

    def import_many(self, data: List[Dict], summary: bool = False) -> Union[List[ImageInstance], Dict]:
        """
        Import data or generate a summary of what would be imported.
        
        Parameters:
        -----------
        data : List[Dict]
            List of patient dictionaries with the structure documented in _import
        summary : bool, default=False
            If True, only generate a summary of what would be imported without actually
            importing the data. If False, perform the actual import.
            
        Returns:
        --------
        Union[List[ImageInstance], Dict]
            If summary=False: The image instances created during the import
            If summary=True: A dictionary containing import statistics
        """
        try:
            if summary:
                return self._summary(data)
            else:
                return self._import(data)
        finally:
            # Always clear collections at the end to ensure stateless behavior
            self._clear_collections()

    def import_one(self, image_data: Dict, summary: bool = False) -> Union[List[ImageInstance], Dict]:
        """
        Import a single image using a simplified flat dictionary structure.
        
        Parameters:
        -----------
        image_data : Dict
            Dictionary containing all the necessary information for importing a single image:
            {
                "project_name": str,              # Required project name
                "patient_identifier": str,        # Optional patient identifier
                "patient_props": dict,            # Optional patient properties
                "study_date": datetime.date,      # Optional study date
                "study_props": dict,              # Optional study properties
                "series_id": str,                 # Optional series identifier
                "series_props": dict,             # Optional series properties
                "image": str,                     # Path to the image file (required)
                "image_props": dict               # Optional image properties
            }
        summary : bool, default=False
            If True, only generate a summary of what would be imported without actually
            importing the data. If False, perform the actual import.
            
        Returns:
        --------
        Union[List[ImageInstance], Dict]
            If summary=False: The image instances created during the import
            If summary=True: A dictionary containing import statistics
        """
        if "project_name" not in image_data:
            raise ValueError("project_name is required in the image_data dictionary")
            
        # Transform the flat dictionary into the nested structure expected by import
        structured_data = [{
            "project_name": image_data.get("project_name"),
            "patient_identifier": image_data.get("patient_identifier"),
            "props": image_data.get("patient_props", {}),
            "studies": [{
                "study_date": image_data.get("study_date"),
                "props": image_data.get("study_props", {}),
                "series": [{
                    "series_id": image_data.get("series_id"),
                    "props": image_data.get("series_props", {}),
                    "images": [{
                        "image": image_data.get("image"),
                        "props": image_data.get("image_props", {})
                    }]
                }]
            }]
        }]
        
        # Call the appropriate method based on the summary flag
        return self.import_many(structured_data, summary=summary)

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

            percentage = (
                (populated_count / total_count * 100) if total_count > 0 else 0
            )

            column_stats.append({
                'Column': column,
                'Populated': populated_count,
                'Percentage': percentage  # Return raw number for easy dataframe creation
            })

        return column_stats
