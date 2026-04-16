from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select

from eyened_orm import (
    DeviceInstance,
    DeviceModel,
    ImageInstance,
    ImageStorage,
    Patient,
    Project,
    Series,
    StorageBackend,
    Study,
)
from eyened_orm.importer.importer import plan_import
from eyened_orm.importer.importer_dtos import ImportRow


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


DEFAULTS = {
    "project_external": "Y",
    "manufacturer": "test-manufacturer",
    "manufacturer_model_name": "test-model",
    "device_description": "test-device-description",
    "dataset_identifier": "",
    "storage_backend_kind": "test-kind",
}


def test_two_phase_import_partial_overlap_reuses_and_updates(session):
    """
    Phase 1: import a small dataset with stable lookup keys.
    Phase 2: re-import a partially overlapping dataset:
    - some rows overlap exactly -> should map to existing objects
    - some rows overlap but change fields -> should produce UPDATEs not CREATEs
    - some rows are new -> should create new rows
    """
    study_date = date(2026, 4, 15)
    series_uid = "SERIES-UID-1"

    # Phase 1: two images in the same patient/study/series.
    rows_phase1 = [
        ImportRow(
            project_name="proj-1",
            project_description="initial project description",
            patient_identifier="pat-1",
            study_date=study_date,
            series_instance_uid=series_uid,
            sop_instance_uid="SOP-1",
            storage_backend_key="sb-1",
            object_key="img-1.png",
            modality="ColorFundus",
            laterality="L",
            image_storage_is_primary=True,
            device_serial_number="SERIAL-A",
        ),
        ImportRow(
            project_name="proj-1",
            patient_identifier="pat-1",
            study_date=study_date,
            series_instance_uid=series_uid,
            sop_instance_uid="SOP-2",
            storage_backend_key="sb-1",
            object_key="img-2.png",
            modality="ColorFundus",
            laterality="R",
            image_storage_is_primary=True,
            device_serial_number="SERIAL-A",
        ),
    ]

    run1 = plan_import(session, rows_phase1, defaults=DEFAULTS)
    run1.apply()
    session.commit()

    assert _count(session, Project) == 1
    assert _count(session, Patient) == 1
    assert _count(session, Study) == 1
    assert _count(session, Series) == 1
    assert _count(session, StorageBackend) == 1
    assert _count(session, DeviceModel) == 1
    assert _count(session, DeviceInstance) == 1
    assert _count(session, ImageInstance) == 2
    assert _count(session, ImageStorage) == 2

    proj = Project.by_name(session, "proj-1")
    assert proj is not None
    assert proj.Description == "initial project description"

    # Phase 2:
    # - SOP-1 overlaps and changes laterality + device_serial_number + project_description
    # - SOP-2 overlaps exactly (no changes)
    # - SOP-3 is new in same series
    # - plus a new series under same study (SERIES-UID-2) with a new image
    rows_phase2 = [
        ImportRow(
            project_name="proj-1",
            project_description="updated project description",
            patient_identifier="pat-1",
            study_date=study_date,
            series_instance_uid=series_uid,
            sop_instance_uid="SOP-1",
            storage_backend_key="sb-1",
            object_key="img-1.png",
            modality="ColorFundus",
            laterality="R",  # changed
            image_storage_is_primary=False,  # changed
            device_serial_number="SERIAL-B",  # changed -> DeviceInstance update
        ),
        ImportRow(
            project_name="proj-1",
            patient_identifier="pat-1",
            study_date=study_date,
            series_instance_uid=series_uid,
            sop_instance_uid="SOP-2",
            storage_backend_key="sb-1",
            object_key="img-2.png",
            modality="ColorFundus",
            laterality="R",
            image_storage_is_primary=True,
            device_serial_number="SERIAL-A",
        ),
        ImportRow(
            project_name="proj-1",
            patient_identifier="pat-1",
            study_date=study_date,
            series_instance_uid=series_uid,
            sop_instance_uid="SOP-3",  # new instance
            storage_backend_key="sb-1",
            object_key="img-3.png",
            modality="ColorFundus",
            laterality="L",
            image_storage_is_primary=True,
            device_serial_number="SERIAL-B",
        ),
        ImportRow(
            project_name="proj-1",
            patient_identifier="pat-1",
            study_date=study_date,
            series_instance_uid="SERIES-UID-2",  # new series under same study
            sop_instance_uid="SOP-4",
            storage_backend_key="sb-1",
            object_key="img-4.png",
            modality="ColorFundus",
            laterality="L",
            image_storage_is_primary=True,
            device_serial_number="SERIAL-B",
            series_number=7,
        ),
    ]

    run2 = plan_import(session, rows_phase2, defaults=DEFAULTS)
    run2.apply()
    session.commit()

    # Reuse existing top-level rows and add the new ones.
    assert _count(session, Project) == 1
    assert _count(session, Patient) == 1
    assert _count(session, Study) == 1
    assert _count(session, Series) == 2  # added SERIES-UID-2
    assert _count(session, StorageBackend) == 1
    assert _count(session, DeviceModel) == 1
    assert _count(session, DeviceInstance) == 1
    assert _count(session, ImageInstance) == 4  # added SOP-3 and SOP-4
    assert _count(session, ImageStorage) == 4

    proj2 = Project.by_name(session, "proj-1")
    assert proj2 is not None
    assert proj2.Description == "updated project description"

    sop1 = ImageInstance.by_column(session, SOPInstanceUid="SOP-1")
    assert sop1 is not None
    assert getattr(sop1.Laterality, "value", sop1.Laterality) == "R"

    storage1 = session.scalar(
        select(ImageStorage).where(ImageStorage.ObjectKey == "img-1.png")
    )
    assert storage1 is not None
    assert storage1.IsPrimary is False

    dev_inst = session.scalar(select(DeviceInstance))
    assert dev_inst is not None
    assert dev_inst.SerialNumber == "SERIAL-B"


def test_mixed_keying_strategies_in_one_batch(session):
    """
    Batch contains:
    - A series identified by SeriesInstanceUid (lookup key)
    - Another series created anonymously via series_anonymous_identity
    - Multiple images grouped into the anonymous series
    """
    base_dt = datetime(2026, 4, 15, 12, 0, 0)
    rows = [
        # Lookup series via SeriesInstanceUid
        ImportRow(
            project_name="proj-keys",
            patient_identifier="pat-keys",
            study_date=base_dt.date(),
            series_instance_uid="SERIES-LOOKUP",
            sop_instance_uid="SOP-L1",
            storage_backend_key="sb-keys",
            object_key="lookup-1.png",
            modality="ColorFundus",
            laterality="L",
        ),
        # Anonymous series grouping: two rows should share the same Series.
        ImportRow(
            project_name="proj-keys",
            patient_identifier="pat-keys",
            study_date=base_dt.date(),
            series_instance_uid=None,
            series_anonymous_identity=123,
            sop_instance_uid="SOP-A1",
            storage_backend_key="sb-keys",
            object_key="anon-1.png",
            modality="ColorFundus",
            laterality="R",
        ),
        ImportRow(
            project_name="proj-keys",
            patient_identifier="pat-keys",
            study_date=base_dt.date(),
            series_instance_uid=None,
            series_anonymous_identity=123,
            sop_instance_uid="SOP-A2",
            storage_backend_key="sb-keys",
            object_key="anon-2.png",
            modality="ColorFundus",
            laterality="L",
        ),
    ]

    run = plan_import(session, rows, defaults=DEFAULTS)
    run.apply()
    session.commit()

    assert _count(session, Project) == 1
    assert _count(session, Patient) == 1
    assert _count(session, Study) == 1
    assert _count(session, Series) == 2  # one lookup series + one anonymous group
    assert _count(session, ImageInstance) == 3
    assert _count(session, ImageStorage) == 3

