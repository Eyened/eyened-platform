from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import lazyload

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
from eyened_orm.importer.importer import plan_image_import
from eyened_orm.importer.importer_dtos import ImportRow


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_plan_image_import_apply_creates_expected_entities_with_defaults(session):
    defaults = {
        "project_external": "Y",
        "manufacturer": "test-manufacturer",
        "manufacturer_model_name": "test-model",
        "device_description": "test-description",
        "dataset_identifier": "",
        "storage_backend_kind": "test-kind",
    }
    rows = [
        ImportRow(
            project_name="test-project",
            storage_backend_key="oogergo",
            object_key=f"test-{i}.png",
            modality="ColorFundus",
            laterality="L",
            patient_identifier="test-patient",
            study_date=datetime.now().date(),
            series_anonymous_identity=1,
        )
        for i in range(3)
    ]

    run = plan_image_import(session, rows, defaults=defaults)
    run.apply()
    session.commit()

    # Project/patient/study/series are deduped via natural keys / anonymous grouping.
    assert _count(session, Project) == 1
    assert _count(session, Patient) == 1
    assert _count(session, Study) == 1
    assert _count(session, Series) == 1

    # DeviceModel/DeviceInstance dedupe via defaults.
    assert _count(session, DeviceModel) == 1
    assert _count(session, DeviceInstance) == 1

    # StorageBackend is shared, object_key unique so 3 ImageStorages.
    assert _count(session, StorageBackend) == 1
    assert _count(session, ImageStorage) == 3

    # ImageInstance is anonymous by default -> one per row.
    assert _count(session, ImageInstance) == 3

    proj = session.scalar(select(Project))
    assert proj is not None
    assert proj.ProjectName == "test-project"
    assert getattr(proj.External, "value", proj.External) == "Y"

    storages = session.scalars(
        select(ImageStorage)
        .options(lazyload("*"))
        .order_by(ImageStorage.ImageStorageID)
    ).all()
    assert [s.ObjectKey for s in storages] == ["test-0.png", "test-1.png", "test-2.png"]
    assert all(s.Format == "image/png" for s in storages)

