from sqlalchemy import func, select

from eyened_orm import AuditLog, ImageInstance
from eyened_orm.importer import import_run as import_run_module


def _import_row(**overrides) -> dict:
    """A minimal but complete flat image-import row (no `defaults=` dict -- the
    route calls `plan_image_import` without one, so every field the entity
    graph needs must be present directly, mirroring
    orm/eyened_orm/importer/tests/test_import_regressions.py::test_import_with_manufacturer_model_name_succeeds."""
    row = {
        "project_name": "test-import-project",
        "project_external": "Y",
        "patient_identifier": "test-patient",
        "study_date": "2026-01-01",
        "series_instance_uid": "test-series-import",
        "manufacturer": "m",
        "manufacturer_model_name": "mm",
        "device_description": "d",
        "dataset_identifier": "",
        "storage_backend_key": "sb-import",
        "storage_backend_kind": "local",
        "object_key": "img-import.png",
        "modality": "ColorFundus",
        "laterality": "L",
    }
    row.update(overrides)
    return row


def test_import_single_image_success_relies_on_get_db_commit_and_audits(client, session):
    """A successful import creates the ImageInstance and records exactly one
    Import/INSERT AuditLog row via AuditService -- committed by get_db, not by
    the handler (no mid-handler session.commit())."""
    response = client.post("/import/image", json={"data": _import_row(), "options": {}})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["image_count"] == 1

    assert session.scalar(select(func.count()).select_from(ImageInstance)) == 1

    audit_rows = session.query(AuditLog).filter_by(Entity="Import").all()
    assert len(audit_rows) == 1
    assert audit_rows[0].Action == "INSERT"
    assert audit_rows[0].Changes == {
        "project_name": "test-import-project",
        "images_created": 1,
    }


def test_import_single_image_failure_rolls_back_and_creates_no_rows(
    client, session, monkeypatch
):
    """A mid-apply exception must leave zero new ImageInstance rows: the handler's
    `except` block must call session.rollback() before returning success=False, or
    get_db's post-yield commit would flush the still-pending entities that
    ImportRun.apply() add_all()'d before the exception.

    Discriminator: delete the `session.rollback()` in import_api.py's except
    block and this test fails (image row count goes from 0 to 1).
    """
    original_apply = import_run_module.ImportUpdate.apply
    calls = {"n": 0}

    def _flaky_apply(self, session):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("forced mid-apply failure")
        return original_apply(self, session)

    monkeypatch.setattr(import_run_module.ImportUpdate, "apply", _flaky_apply)

    before = session.scalar(select(func.count()).select_from(ImageInstance))

    response = client.post(
        "/import/image",
        json={"data": _import_row(series_instance_uid="test-series-fail"), "options": {}},
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is False

    after = session.scalar(select(func.count()).select_from(ImageInstance))
    assert after == before
    assert session.query(AuditLog).filter_by(Entity="Import").count() == 0
