from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select

from eyened_orm import ImageStorage, Project
from eyened_orm.importer.importer import plan_image_import
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
        run = plan_image_import(s1, rows, defaults=defaults)
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


def test_undo_stored_run_after_later_import_preserves_other_project(SessionLocal, tmp_path):
    """Persist first ``ImportRun`` to JSON, run a second import, then undo the first run; the second project remains."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "test-manufacturer",
        "manufacturer_model_name": "test-model",
        "device_description": "test-description",
        "dataset_identifier": "",
        "storage_backend_kind": "test-kind",
    }
    d = date(2026, 8, 1)
    rows_a = [
        ImportRow(
            project_name="undo-a-proj",
            patient_identifier="pa",
            study_date=d,
            series_instance_uid="undo-a-ser",
            storage_backend_key="sb-undo-a",
            object_key="undo-a-0.png",
            modality="ColorFundus",
            laterality="L",
            manufacturer="dev-undo-a",
            manufacturer_model_name="model-undo-a",
            device_description="desc-a",
        )
    ]
    rows_b = [
        ImportRow(
            project_name="undo-b-proj",
            patient_identifier="pb",
            study_date=d,
            series_instance_uid="undo-b-ser",
            storage_backend_key="sb-undo-b",
            object_key="undo-b-0.png",
            modality="ColorFundus",
            laterality="R",
            manufacturer="dev-undo-b",
            manufacturer_model_name="model-undo-b",
            device_description="desc-b",
        )
    ]

    path_a = tmp_path / "run_a.json"

    with SessionLocal() as s1:
        run_a = plan_image_import(s1, rows_a, defaults=defaults)
        run_a.apply()
        s1.commit()
        run_a.write_json(path_a)
        assert _count(s1, Project) == 1

    with SessionLocal() as s2:
        run_b = plan_image_import(s2, rows_b, defaults=defaults)
        run_b.apply()
        s2.commit()
        assert _count(s2, Project) == 2

    with SessionLocal() as s3:
        loaded_a = ImportRun.read_json(s3, path_a)
        loaded_a.undo()
        s3.commit()

        assert _count(s3, Project) == 1
        assert Project.by_name(s3, "undo-a-proj") is None
        assert Project.by_name(s3, "undo-b-proj") is not None

