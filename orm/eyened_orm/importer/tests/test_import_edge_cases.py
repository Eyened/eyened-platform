from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select

from eyened_orm import ImageStorage, Patient, Project
from eyened_orm.importer.importer import plan_image_import
from eyened_orm.importer.importer_dtos import ImportRow


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_missing_project_identification_rejected(session):
    # Project requires either an existing project_id, a resolvable project_name, or a
    # non-null project_name for anonymous creation. Leaving both empty should fail
    # early (before apply/flush), because we can't build the required entity graph.
    rows = [
        ImportRow(
            project_name=None,
            project_id=None,
            storage_backend_key="sb",
            storage_backend_kind="test-kind",
            object_key="x.png",
            patient_identifier="p1",
            manufacturer="m",
            manufacturer_model_name="mm",
            device_description="d",
            study_date=datetime.now().date(),
        )
    ]

    with pytest.raises(RuntimeError, match="Missing parent"):
        plan_image_import(session, rows)


def test_anonymous_project_creation_creates_project_and_links_downstream(session):
    rows = [
        ImportRow(
            project_name="new",
            project_id=None,
            project_external="Y",
            dataset_identifier="",
            patient_identifier="p1",
            study_date=datetime.now().date(),
            series_anonymous_identity=1,
            manufacturer="m",
            manufacturer_model_name="mm",
            device_description="d",
            storage_backend_key="sb",
            storage_backend_kind="test-kind",
            object_key="x.png",
        )
    ]

    run = plan_image_import(session, rows)
    run.apply()
    session.commit()

    assert _count(session, Project) == 1
    assert _count(session, Patient) == 1

    proj = Project.by_name(session, "new")
    assert proj is not None

    storage = session.scalar(select(ImageStorage))
    assert storage is not None

    # Ensure the full parent chain is linked to the created Project.
    assert storage.ImageInstance is not None
    assert storage.ImageInstance.Series is not None
    assert storage.ImageInstance.Series.Study is not None
    assert storage.ImageInstance.Series.Study.Patient is not None
    assert storage.ImageInstance.Series.Study.Patient.Project is proj


def test_two_rows_same_image_storage_lookup_key_dedupes_and_merges_updates(session):
    rows = [
        ImportRow(
            project_name="dedupe-proj",
            project_external="Y",
            dataset_identifier="",
            patient_identifier="p1",
            study_date=datetime.now().date(),
            series_anonymous_identity=1,
            image_anonymous_identity=1,
            manufacturer="m",
            manufacturer_model_name="mm",
            device_description="d",
            storage_backend_key="sb",
            storage_backend_kind="test-kind",
            object_key="same.png",
        ),
        # Same (storage_backend_key, object_key) => same ImageStorage lookup key.
        # Keep ImageInstance consistent via image_anonymous_identity.
        ImportRow(
            project_name="dedupe-proj",
            project_external="Y",
            dataset_identifier="",
            patient_identifier="p1",
            study_date=datetime.now().date(),
            series_anonymous_identity=1,
            image_anonymous_identity=1,
            storage_backend_key="sb",
            storage_backend_kind="test-kind",
            object_key="same.png",
            image_storage_is_primary=True,
        ),
    ]

    run = plan_image_import(session, rows)
    run.apply()
    session.commit()

    assert _count(session, ImageStorage) == 1
    storage = session.scalar(select(ImageStorage))
    assert storage is not None
    assert storage.ObjectKey == "same.png"
    assert storage.IsPrimary is True

    # Guardrail: ensure we didn't plan multiple ImageStorage creates.
    image_storage_creates = [
        c
        for c in run.changes
        if getattr(c, "name", None) == "CREATE"
        and getattr(getattr(c, "entity", None), "__class__", None) is ImageStorage
    ]
    assert len(image_storage_creates) == 1


def test_idempotency_same_import_twice_produces_no_changes_second_time(session):
    rows = [
        ImportRow(
            project_name="idem-proj",
            project_external="Y",
            dataset_identifier="",
            patient_identifier="p1",
            study_date=datetime.now().date(),
            series_anonymous_identity=1,
            image_anonymous_identity=1,
            manufacturer="m",
            manufacturer_model_name="mm",
            device_description="d",
            storage_backend_key="sb",
            storage_backend_kind="test-kind",
            object_key="x.png",
            image_storage_is_primary=True,
        )
    ]

    run1 = plan_image_import(session, rows)
    assert len(run1.changes) > 0
    run1.apply()
    session.commit()

    counts_after_1 = {
        "projects": _count(session, Project),
        "patients": _count(session, Patient),
        "storages": _count(session, ImageStorage),
    }

    run2 = plan_image_import(session, rows)
    assert run2.changes == []
    run2.apply()
    session.commit()

    counts_after_2 = {
        "projects": _count(session, Project),
        "patients": _count(session, Patient),
        "storages": _count(session, ImageStorage),
    }
    assert counts_after_2 == counts_after_1


def test_provided_pk_wins_over_lookup_allows_changing_lookup_fields(session):
    # Pass 1: create Project + Patient via lookup keys.
    run1 = plan_image_import(
        session,
        [
            ImportRow(
                project_name="pk-proj",
                project_external="Y",
                patient_identifier="p-old",
            )
        ],
    )
    run1.apply()
    session.commit()

    assert _count(session, Project) == 1
    assert _count(session, Patient) == 1

    proj1 = Project.by_name(session, "pk-proj")
    assert proj1 is not None
    patient1 = session.scalar(select(Patient))
    assert patient1 is not None
    patient1_id = patient1.PatientID
    proj1_id = proj1.ProjectID

    # Pass 2: provide PKs, but change the lookup fields. This must update the
    # existing rows rather than creating new ones based on the new lookup keys.
    run2 = plan_image_import(
        session,
        [
            ImportRow(
                project_id=proj1_id,
                project_name="pk-proj-renamed",
                patient_id=patient1_id,
                patient_identifier="p-new",
            )
        ],
    )
    run2.apply()
    session.commit()

    assert _count(session, Project) == 1
    assert _count(session, Patient) == 1

    proj2 = session.scalar(select(Project))
    assert proj2 is not None
    assert proj2.ProjectID == proj1_id
    assert proj2.ProjectName == "pk-proj-renamed"

    patient2 = session.scalar(select(Patient))
    assert patient2 is not None
    assert patient2.PatientID == patient1_id
    assert patient2.PatientIdentifier == "p-new"
