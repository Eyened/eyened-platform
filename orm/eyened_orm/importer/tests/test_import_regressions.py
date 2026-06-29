import datetime

import pytest

from eyened_orm import Laterality, ModalityType
from eyened_orm.importer import ImportRow, plan_image_import

GH119_DEFAULTS = {
    "device_description": "unknown",
    "dataset_identifier": "",
    "project_external": "N",
    "storage_backend_kind": "local",
}


def _gh119_row(**extra) -> ImportRow:
    return ImportRow(
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
        **extra,
    )


def test_import_missing_manufacturer_model_name_raises_informative_error(session):
    """
    GH #119: manufacturer is present and device_description comes from defaults,
    but manufacturer_model_name is missing so DeviceModel/DeviceInstance cannot
    be resolved and ImageInstance creation fails with a actionable message.
    """
    with pytest.raises(
        RuntimeError,
        match=(
            r"Cannot create ImageInstance: cannot resolve DeviceInstance; "
            r"provide row field\(s\): manufacturer_model_name"
        ),
    ):
        plan_image_import(session, [_gh119_row()], defaults=GH119_DEFAULTS)


def test_import_with_manufacturer_model_name_succeeds(session):
    run = plan_image_import(
        session,
        [_gh119_row(manufacturer_model_name="Spectralis")],
        defaults=GH119_DEFAULTS,
    )
    assert len(run.changes) > 0
    run.apply()
    session.commit()
