from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from eyened_orm import ImageInstance, ImageStorage, Patient, Project, Series, Study
from eyened_orm.importer.importer import plan_image_import
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


def _base_image_row(
    *,
    sop_instance_uid: str,
    object_key: str,
    series_uid: str = "SERIES-IDEM-1",
    project_name: str = "proj-idem",
    patient_identifier: str = "pat-idem",
    study_date: date | None = None,
) -> ImportRow:
    d = study_date or date(2026, 5, 1)
    return ImportRow(
        project_name=project_name,
        patient_identifier=patient_identifier,
        study_date=d,
        series_instance_uid=series_uid,
        sop_instance_uid=sop_instance_uid,
        storage_backend_key="sb-idem",
        object_key=object_key,
        modality="ColorFundus",
        laterality="L",
        image_storage_is_primary=True,
        device_serial_number="SERIAL-IDEM",
    )


def test_identical_reimport_produces_no_import_run_changes(session):
    """
    Running the same logical import twice should not create duplicate entities and
    should record no CREATE/UPDATE operations on the second run when data matches.
    """
    rows = [
        _base_image_row(sop_instance_uid="SOP-IDEM-1", object_key="idem-1.png"),
    ]
    run1 = plan_image_import(session, rows, defaults=DEFAULTS)
    assert len(run1.changes) > 0
    run1.apply()
    session.commit()

    n_proj = _count(session, Project)
    n_img = _count(session, ImageInstance)
    n_sto = _count(session, ImageStorage)

    run2 = plan_image_import(
        session,
        [
            _base_image_row(sop_instance_uid="SOP-IDEM-1", object_key="idem-1.png"),
        ],
        defaults=DEFAULTS,
    )
    assert len(run2.changes) == 0
    run2.apply()
    session.commit()

    assert _count(session, Project) == n_proj
    assert _count(session, ImageInstance) == n_img
    assert _count(session, ImageStorage) == n_sto


def test_sequential_imports_two_batches_equivalent_to_cumulative_state(session):
    """
    Simulate two "files": first batch inserts one image; second batch adds another
    in the same series. Final row counts should match importing both rows in one
    batch (no duplicate hierarchy rows).
    """
    study_date = date(2026, 5, 2)
    series_uid = "SERIES-TWO-FILE"

    batch1 = [
        ImportRow(
            project_name="proj-2file",
            patient_identifier="pat-2file",
            study_date=study_date,
            series_instance_uid=series_uid,
            sop_instance_uid="SOP-F1",
            storage_backend_key="sb-2file",
            object_key="file1.png",
            modality="ColorFundus",
            laterality="L",
            device_serial_number="SER-2F",
        ),
    ]
    r1 = plan_image_import(session, batch1, defaults=DEFAULTS)
    r1.apply()
    session.commit()

    assert _count(session, ImageInstance) == 1
    assert _count(session, Series) == 1

    batch2 = [
        ImportRow(
            project_name="proj-2file",
            patient_identifier="pat-2file",
            study_date=study_date,
            series_instance_uid=series_uid,
            sop_instance_uid="SOP-F2",
            storage_backend_key="sb-2file",
            object_key="file2.png",
            modality="ColorFundus",
            laterality="R",
            device_serial_number="SER-2F",
        ),
    ]
    r2 = plan_image_import(session, batch2, defaults=DEFAULTS)
    r2.apply()
    session.commit()

    assert _count(session, Project) == 1
    assert _count(session, Patient) == 1
    assert _count(session, Study) == 1
    assert _count(session, Series) == 1
    assert _count(session, ImageInstance) == 2
    assert _count(session, ImageStorage) == 2

    assert (
        ImageInstance.by_column(session, SOPInstanceUid="SOP-F1") is not None
    )
    assert (
        ImageInstance.by_column(session, SOPInstanceUid="SOP-F2") is not None
    )


def test_reimport_subset_of_rows_leaves_sibling_entities_untouched(session):
    """
    Import two images, then run a second import containing only one of the same
    rows (identical keys). The other image must remain; counts stay at two and
    the second run should not create duplicate operations for the repeated row.
    """
    study_date = date(2026, 5, 3)
    series_uid = "SERIES-SUBSET"

    def row(sop: str, key: str, laterality: str) -> ImportRow:
        return ImportRow(
            project_name="proj-sub",
            patient_identifier="pat-sub",
            study_date=study_date,
            series_instance_uid=series_uid,
            sop_instance_uid=sop,
            storage_backend_key="sb-sub",
            object_key=key,
            modality="ColorFundus",
            laterality=laterality,
            device_serial_number="SER-SUB",
        )

    full = [row("SOP-S1", "sub-1.png", "L"), row("SOP-S2", "sub-2.png", "R")]
    plan_image_import(session, full, defaults=DEFAULTS).apply()
    session.commit()

    assert _count(session, ImageInstance) == 2

    partial = plan_image_import(session, [row("SOP-S1", "sub-1.png", "L")], defaults=DEFAULTS)
    assert len(partial.changes) == 0
    partial.apply()
    session.commit()

    assert _count(session, ImageInstance) == 2
    assert ImageInstance.by_column(session, SOPInstanceUid="SOP-S2") is not None


def test_second_full_import_overwrites_mutable_fields_without_duplicates(session):
    """
    Re-import the same natural keys with changed mutable columns: one row per
    entity, updates applied, no extra ImageInstance / ImageStorage rows.
    """
    study_date = date(2026, 5, 4)
    series_uid = "SERIES-OVERWRITE"

    row_v1 = ImportRow(
        project_name="proj-ow",
        project_description="description v1",
        patient_identifier="pat-ow",
        study_date=study_date,
        series_instance_uid=series_uid,
        sop_instance_uid="SOP-OW1",
        storage_backend_key="sb-ow",
        object_key="ow-1.png",
        modality="ColorFundus",
        laterality="L",
        image_storage_is_primary=True,
        device_serial_number="SER-OW-A",
    )
    plan_image_import(session, [row_v1], defaults=DEFAULTS).apply()
    session.commit()

    proj = Project.by_name(session, "proj-ow")
    assert proj is not None
    assert proj.Description == "description v1"

    row_v2 = ImportRow(
        project_name="proj-ow",
        project_description="description v2",
        patient_identifier="pat-ow",
        study_date=study_date,
        series_instance_uid=series_uid,
        sop_instance_uid="SOP-OW1",
        storage_backend_key="sb-ow",
        object_key="ow-1.png",
        modality="ColorFundus",
        laterality="R",
        image_storage_is_primary=False,
        device_serial_number="SER-OW-B",
    )
    run2 = plan_image_import(session, [row_v2], defaults=DEFAULTS)
    assert len(run2.changes) > 0
    run2.apply()
    session.commit()

    assert _count(session, Project) == 1
    assert _count(session, ImageInstance) == 1
    assert _count(session, ImageStorage) == 1

    session.refresh(proj)
    assert proj.Description == "description v2"

    img = ImageInstance.by_column(session, SOPInstanceUid="SOP-OW1")
    assert img is not None
    assert getattr(img.Laterality, "value", img.Laterality) == "R"

    st = session.scalar(select(ImageStorage).where(ImageStorage.ObjectKey == "ow-1.png"))
    assert st is not None
    assert st.IsPrimary is False
