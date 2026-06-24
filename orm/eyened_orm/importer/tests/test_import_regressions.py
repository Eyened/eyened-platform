import datetime

from eyened_orm import Laterality, ModalityType
from eyened_orm.importer import ImportRow, plan_image_import


def test_import_missing_parent_exception_gh119(session):
    """
    Minimal example of an import row that results in a 'Missing parent' exception.

    Problem description in GH issue #119.
    """
    row = ImportRow(
        sop_instance_uid="1.2.276.0.30.1.53.712813.12345672024052413280547317712",
        dicom_modality=ModalityType.OP,
        laterality=Laterality.R,
        height=768,
        width=768,
        manufacturer="Heidelberg Engineering",
        samples_per_pixel=1,
        sop_class_uid="1.2.840.10008.5.1.4.1.1.7",
        photometric_interpretation="MONOCHROME2",
        project_name="Myopia",
        patient_identifier="010047",
        study_date=datetime.date(2024, 5, 24),
        series_instance_uid="1.2.276.0.30.3.17.2024052413280547.123456749712",
        study_instance_uid="1.2.276.0.30.2.2024052413280547.4524051.123456753",
        storage_backend_key="images",
        object_key="heyex/MC13/12345/987654/2901952/20240524132805.djptdxp1.x4p.1.dcm",
    )
    defaults = {
        "device_description": "unknown",
        "dataset_identifier": "",
        "project_external": "N",
    }
    # This raises: RuntimeError: Missing parent DeviceInstance for ImageInstance
    run = plan_image_import(session, [row], defaults=defaults)
