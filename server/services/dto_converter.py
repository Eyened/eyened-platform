"""
DTO Conversion Service
Handles conversion between ORM objects and DTOs without extending ORM classes.
This provides a clean separation between the ORM layer and API layer.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from eyened_orm import (
        Study, Patient, Series, ImageInstance, Project, Creator,
        DeviceModel, DeviceInstance, Scan
    )
    from ..routes.dtos import (
        StudyOutput, StudyBrowser, PatientOutput, SeriesOutput, SeriesBrowser,
        InstanceOutput, ProjectOutput, CreatorOutput, DeviceModelOutput,
        DeviceInstanceOutput, ScanOutput
    )


class DTOConverter:
    """Service class for converting ORM objects to DTOs."""

    @staticmethod
    def project_to_dto(project: 'Project'):
        """Convert Project ORM object to ProjectOutput DTO."""
        from ..routes.dtos import ProjectOutput
        
        return ProjectOutput(
            id=project.ProjectID,
            name=project.ProjectName,
            external=project.External.value == 1,  # Convert enum to boolean
            description=project.Description,
        )

    @staticmethod
    def patient_to_dto(patient: 'Patient'):
        """Convert Patient ORM object to PatientOutput DTO."""
        from ..routes.dtos import PatientOutput
        
        # Convert SexEnum to string if present
        sex_str = None
        if patient.Sex is not None:
            sex_str = patient.Sex.name  # Convert enum to string ("M" or "F")
        
        return PatientOutput(
            id=patient.PatientID,
            identifier=patient.PatientIdentifier or "",
            birth_date=patient.BirthDate,
            sex=sex_str
        )
    
    @staticmethod
    def study_to_dto(study: 'Study', browser: bool = False):
        """Convert Study ORM object to StudyOutput or StudyBrowser DTO."""
        from ..routes.dtos import StudyOutput, StudyBrowser
        
        if not browser:
            return StudyOutput(
                id=study.StudyID,
                date=study.StudyDate,
                study_instance_uid=study.StudyInstanceUid,
                description=study.StudyDescription,
            )
        else:
            return StudyBrowser(
                id=study.StudyID,
                description=study.StudyDescription,
                study_instance_uid=study.StudyInstanceUid,
                date=study.StudyDate,
                patient=DTOConverter.patient_to_dto(study.Patient),
                series=[DTOConverter.series_to_dto(s, browser=False) for s in study.Series],
            )
    
    
    
    @staticmethod
    def series_to_dto(series: 'Series', browser: bool = False):
        """Convert Series ORM object to SeriesOutput or SeriesBrowser DTO."""
        from ..routes.dtos import SeriesOutput, SeriesBrowser
        
        if not browser:
            return SeriesOutput(
                id=series.SeriesID,
                series_number=series.SeriesNumber,
                series_instance_uid=series.SeriesInstanceUid,
            )
        else:
            return SeriesBrowser(
                id=series.SeriesID,
                series_number=series.SeriesNumber,
                series_instance_uid=series.SeriesInstanceUid,
                instances=[DTOConverter.image_instance_to_dto(instance) for instance in series.ImageInstances],
            )
    
    @staticmethod
    def image_instance_to_dto(image_instance: 'ImageInstance'):
        """Convert ImageInstance ORM object to InstanceOutput DTO."""
        from ..routes.dtos import InstanceOutput, DeviceMerged, ScanOutput
        
        # Create device info - handle case where DeviceInstance might be None
        device_data = {}
        if image_instance.DeviceInstance and image_instance.DeviceInstance.DeviceModel:
            device_data = {
                "device_model_id": image_instance.DeviceInstance.DeviceModelID,
                "serial_number": image_instance.DeviceInstance.SerialNumber,
                "description": image_instance.DeviceInstance.Description,
                "manufacturer": image_instance.DeviceInstance.DeviceModel.Manufacturer,
                "model": image_instance.DeviceInstance.DeviceModel.ManufacturerModelName,
            }
        else:
            # Provide default values if device info is missing
            device_data = {
                "device_model_id": 0,
                "serial_number": None,
                "description": None,
                "manufacturer": "Unknown",
                "model": "Unknown",
            }
        
        device = DeviceMerged(**device_data)
        
        return InstanceOutput(
            id=image_instance.ImageInstanceID,
            sop_instance_uid=image_instance.SOPInstanceUid or "",
            dataset_identifier=image_instance.DatasetIdentifier,
            thumbnail_identifier=image_instance.ThumbnailIdentifier or "",
            thumbnail_path=str(image_instance.thumbnail_path) if image_instance.ThumbnailIdentifier else "",
            modality=image_instance.Modality.name if image_instance.Modality else "",
            dicom_modality=image_instance.DICOMModality.name if image_instance.DICOMModality else "",
            etdrs_field=image_instance.ETDRSField.name if image_instance.ETDRSField else "",
            angio_graphy=str(image_instance.Angiography) if image_instance.Angiography else "",
            laterality=image_instance.Laterality.name if image_instance.Laterality else "L",
            anatomic_region=str(image_instance.AnatomicRegion) if image_instance.AnatomicRegion else "",
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
            project=DTOConverter.project_to_dto(image_instance.Series.Study.Patient.Project),
            patient=DTOConverter.patient_to_dto(image_instance.Series.Study.Patient),
            study=DTOConverter.study_to_dto(image_instance.Series.Study),
            series=DTOConverter.series_to_dto(image_instance.Series),
            device=device,
            scan=DTOConverter.scan_to_dto(image_instance.Scan) if image_instance.Scan else ScanOutput(id=0, mode="Unknown"),
        )
    
    
    
    @staticmethod
    def creator_to_dto(creator: 'Creator'):
        """Convert Creator ORM object to CreatorOutput DTO."""
        from ..routes.dtos import CreatorOutput
        
        return CreatorOutput(
            id=creator.CreatorID,
            name=creator.CreatorName,
            msn=creator.MSN,
            is_human=creator.IsHuman,
            description=creator.Description,
            version=str(creator.Version) if creator.Version else None,
            role=creator.Role,
            date_inserted=creator.DateInserted,
        )
    
    @staticmethod
    def device_model_to_dto(device_model: 'DeviceModel'):
        """Convert DeviceModel ORM object to DeviceModelOutput DTO."""
        from ..routes.dtos import DeviceModelOutput
        
        return DeviceModelOutput(
            id=device_model.DeviceModelID,
            manufacturer=device_model.Manufacturer,
            model=device_model.ManufacturerModelName,
        )
    
    @staticmethod
    def device_instance_to_dto(device_instance: 'DeviceInstance'):
        """Convert DeviceInstance ORM object to DeviceInstanceOutput DTO."""
        from ..routes.dtos import DeviceInstanceOutput
        
        return DeviceInstanceOutput(
            id=device_instance.DeviceInstanceID,
            device_model_id=device_instance.DeviceModelID,
            serial_number=device_instance.SerialNumber,
            description=device_instance.Description,
        )
    
    @staticmethod
    def scan_to_dto(scan: 'Scan'):
        """Convert Scan ORM object to ScanOutput DTO."""
        from ..routes.dtos import ScanOutput
        
        return ScanOutput(
            id=scan.ScanID,
            mode=scan.Mode,
        )
    
    # Convenience methods for bulk conversions
    @staticmethod
    def studies_to_dtos(studies, browser: bool = False):
        """Convert a list of Study objects to DTOs."""
        return [DTOConverter.study_to_dto(study, browser=browser) for study in studies]
    
    @staticmethod
    def patients_to_dtos(patients):
        """Convert a list of Patient objects to DTOs."""
        return [DTOConverter.patient_to_dto(patient) for patient in patients]
    
    @staticmethod
    def series_to_dtos(series_list, browser: bool = False):
        """Convert a list of Series objects to DTOs."""
        return [DTOConverter.series_to_dto(series, browser=browser) for series in series_list]
    
    @staticmethod
    def image_instances_to_dtos(image_instances):
        """Convert a list of ImageInstance objects to DTOs."""
        return [DTOConverter.image_instance_to_dto(instance) for instance in image_instances]


# Convenience aliases for shorter imports
to_study_dto = DTOConverter.study_to_dto
to_patient_dto = DTOConverter.patient_to_dto
to_series_dto = DTOConverter.series_to_dto
to_image_instance_dto = DTOConverter.image_instance_to_dto
to_project_dto = DTOConverter.project_to_dto
to_creator_dto = DTOConverter.creator_to_dto
to_device_model_dto = DTOConverter.device_model_to_dto
to_device_instance_dto = DTOConverter.device_instance_to_dto
to_scan_dto = DTOConverter.scan_to_dto

# Bulk conversion aliases
to_studies_dtos = DTOConverter.studies_to_dtos
to_patients_dtos = DTOConverter.patients_to_dtos
to_series_dtos = DTOConverter.series_to_dtos
to_image_instances_dtos = DTOConverter.image_instances_to_dtos 