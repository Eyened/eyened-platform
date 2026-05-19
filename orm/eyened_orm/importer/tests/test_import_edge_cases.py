from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from eyened_orm import ImageInstance, ImageStorage, Patient, Project
from eyened_orm.importer.importer import plan_image_import
from eyened_orm.importer.importer_dtos import ImportRow


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_missing_project_identification_rejected(session):
    # Project requires either project_id, resolvable project_name, or enough context to build
    # the graph. Leaving both project_id and project_name empty should fail during planning.
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


def test_image_anonymous_identity_one_instance_two_storages(session):
    """No SOP/PublicID: shared ``image_anonymous_identity`` merges instance; distinct ``object_key`` yields two storages."""
    d = date(2026, 6, 15)
    anon = 77
    common = dict(
        project_name="anon-img-2stor",
        project_external="Y",
        dataset_identifier="",
        patient_identifier="p1",
        study_date=d,
        series_anonymous_identity=1,
        image_anonymous_identity=anon,
        manufacturer="m",
        manufacturer_model_name="mm",
        device_description="d",
        storage_backend_key="sb-2stor",
        storage_backend_kind="test-kind",
        modality="ColorFundus",
        laterality="L",
    )
    rows = [
        ImportRow(
            **common,
            object_key="first.png",
            image_storage_is_primary=False,
        ),
        ImportRow(
            **common,
            object_key="second.png",
            image_storage_is_primary=True,
        ),
    ]

    run = plan_image_import(session, rows)
    run.apply()
    session.commit()

    assert _count(session, ImageInstance) == 1
    assert _count(session, ImageStorage) == 2
    storages = session.scalars(select(ImageStorage)).all()
    keys = {s.ObjectKey for s in storages}
    assert keys == {"first.png", "second.png"}
    assert sum(1 for s in storages if s.IsPrimary) == 1
    assert sum(1 for s in storages if not s.IsPrimary) == 1


def test_idempotency_same_import_twice_produces_no_changes_second_time(session):
    rows = [
        ImportRow(
            project_name="idem-proj",
            project_external="Y",
            dataset_identifier="",
            patient_identifier="p1",
            study_date=datetime.now().date(),
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
