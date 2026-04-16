from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from eyened_orm import ImageStorage, Project
from eyened_orm.importer.importer import plan_import
from eyened_orm.importer.importer_dtos import ImportRow
from eyened_orm.importer.import_run import ImportRun


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_import_run_json_roundtrip_undo_new_session(SessionLocal, tmp_path):
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
        for i in range(2)
    ]

    with SessionLocal() as s1:
        run = plan_import(s1, rows, defaults=defaults)
        run.apply()
        s1.commit()

        assert run.status == "done"
        assert _count(s1, Project) == 1
        assert _count(s1, ImageStorage) == 2

        json_path = tmp_path / "import_run.json"
        run.write_json(json_path)

    # New session: read json, undo, commit.
    with SessionLocal() as s2:
        loaded = ImportRun.read_json(s2, json_path)
        loaded.undo()
        s2.commit()

        assert loaded.status == "cancelled"
        assert _count(s2, Project) == 0
        assert _count(s2, ImageStorage) == 0

