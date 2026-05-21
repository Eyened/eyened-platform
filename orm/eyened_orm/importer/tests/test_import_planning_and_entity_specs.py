"""Tests for contact-on-project, series/image identity keys, prepare defaults, and ``entity_specs`` graph validation."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from eyened_orm import Contact, ImageInstance, Project, Series, Study, Patient
from eyened_orm.importer.importer import (
    build_image_import_rows,
    entity_build_order,
    plan_image_import,
    plan_import,
)
from eyened_orm.importer.importer_dtos import ImportRow
from eyened_orm.importer.importer_mappings_image import ENTITY_SPECS
from eyened_orm.project import ExternalEnum


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_contact_from_row_attaches_to_project(session):
    """Natural ``contact_*`` fields on ``ImportRow`` create or reuse ``Contact`` and set ``Project.ContactID``."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "m",
        "manufacturer_model_name": "mm",
        "device_description": "d",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    d = date(2026, 6, 1)
    rows = [
        ImportRow(
            project_name="proj-with-contact",
            patient_identifier="pat-c",
            study_date=d,
            series_instance_uid="ser-c",
            contact_name="Dr. Contact",
            contact_email="contact@example.org",
            contact_institute="Institute A",
            storage_backend_key="sb-c",
            object_key="img-c.png",
            modality="ColorFundus",
            laterality="L",
        )
    ]
    run = plan_image_import(session, rows, defaults=defaults)
    run.apply()
    session.commit()

    assert _count(session, Contact) == 1
    c = session.scalar(select(Contact))
    assert c is not None
    assert c.Name == "Dr. Contact"
    assert c.Email == "contact@example.org"
    assert c.Institute == "Institute A"

    proj = Project.by_name(session, "proj-with-contact")
    assert proj is not None
    assert proj.ContactID == c.ContactID
    assert proj.Contact is not None


def test_series_anonymous_key_groups_images_without_series_uid(session):
    """Shared ``series_anonymous_identity`` without ``series_instance_uid`` yields a single ``Series``."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "m",
        "manufacturer_model_name": "mm",
        "device_description": "d",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    d = date(2026, 6, 2)
    anon = 4242
    rows = [
        ImportRow(
            project_name="proj-anon-ser",
            patient_identifier="pat-s",
            study_date=d,
            series_anonymous_identity=anon,
            sop_instance_uid=f"SOP-ANON-SER-{i}",
            manufacturer="m",
            manufacturer_model_name="mm",
            device_description="d",
            storage_backend_key="sb-s",
            object_key=f"anon-ser-{i}.png",
            modality="ColorFundus",
            laterality="L",
        )
        for i in range(3)
    ]
    run = plan_image_import(session, rows, defaults=defaults)
    run.apply()
    session.commit()

    assert _count(session, Series) == 1
    s = session.scalar(select(Series))
    assert s is not None
    assert s.SeriesInstanceUid is None


def test_series_anonymous_identity_scoped_per_study_not_across_patients(session):
    """Same ``series_anonymous_identity`` on different studies yields separate ``Series``."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "m",
        "manufacturer_model_name": "mm",
        "device_description": "d",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    d = date(2026, 6, 10)
    anon = 9001
    rows = [
        ImportRow(
            project_name="proj-anon-scope",
            patient_identifier="pat-a",
            study_date=d,
            series_anonymous_identity=anon,
            sop_instance_uid="SOP-ANON-SCOPE-A",
            manufacturer="m",
            manufacturer_model_name="mm",
            device_description="d",
            storage_backend_key="sb-scope",
            object_key="anon-scope-a.png",
            modality="ColorFundus",
            laterality="L",
        ),
        ImportRow(
            project_name="proj-anon-scope",
            patient_identifier="pat-b",
            study_date=d,
            series_anonymous_identity=anon,
            sop_instance_uid="SOP-ANON-SCOPE-B",
            manufacturer="m",
            manufacturer_model_name="mm",
            device_description="d",
            storage_backend_key="sb-scope",
            object_key="anon-scope-b.png",
            modality="ColorFundus",
            laterality="R",
        ),
    ]
    run = plan_image_import(session, rows, defaults=defaults)
    run.apply()
    session.commit()

    assert _count(session, Patient) == 2
    assert _count(session, Study) == 2
    assert _count(session, Series) == 2


def test_sop_natural_key_ignores_conflicting_public_id_on_followup_import(session):
    """First lookup on ``ImageInstance`` is ``SOPInstanceUid``; a later row cannot replace ``PublicID`` (non-mutable)."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "m",
        "manufacturer_model_name": "mm",
        "device_description": "d",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    d = date(2026, 6, 3)
    sop = "SOP-PREC-UNIQUE-001"
    pub_other = "999999999999"

    run1 = plan_image_import(
        session,
        [
            ImportRow(
                project_name="proj-prec",
                patient_identifier="pat-p",
                study_date=d,
                series_instance_uid="ser-p",
                sop_instance_uid=sop,
                storage_backend_key="sb-p",
                object_key="first.png",
                modality="ColorFundus",
                laterality="L",
            )
        ],
        defaults=defaults,
    )
    run1.apply()
    session.commit()

    img = ImageInstance.by_column(session, SOPInstanceUid=sop)
    assert img is not None
    pub_after_first = img.PublicID

    run2 = plan_image_import(
        session,
        [
            ImportRow(
                project_name="proj-prec",
                patient_identifier="pat-p",
                study_date=d,
                series_instance_uid="ser-p",
                sop_instance_uid=sop,
                public_id=pub_other,
                storage_backend_key="sb-p",
                object_key="second.png",
                modality="ColorFundus",
                laterality="R",
            )
        ],
        defaults=defaults,
    )
    run2.apply()
    session.commit()

    session.refresh(img)
    assert img.PublicID == pub_after_first
    assert img.Laterality.value == "R"


def test_build_image_rows_applies_defaults_for_plan_import(session):
    """``build_image_import_rows`` merges ``defaults``; ``plan_import`` on the prepared rows persists required fields."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "m",
        "manufacturer_model_name": "mm",
        "device_description": "d",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    d = date(2026, 6, 4)
    raw = ImportRow(
        project_name="proj-def-split",
        patient_identifier="pat-d",
        study_date=d,
        series_instance_uid="ser-d",
        storage_backend_key="sb-d",
        object_key="def.png",
        modality="ColorFundus",
        laterality="L",
    )
    assert raw.project_external is None

    prepared = build_image_import_rows([raw], defaults=defaults)
    assert len(prepared) == 1
    assert prepared[0].project_external == ExternalEnum.Y
    assert prepared[0].manufacturer == "m"

    run = plan_import(session, prepared)
    run.apply()
    session.commit()

    proj = Project.by_name(session, "proj-def-split")
    assert proj is not None
    assert proj.External == ExternalEnum.Y


def test_entity_build_order_rejects_specs_missing_implied_parents(session):
    """``entity_build_order`` requires every ``implies`` parent to appear in ``entity_specs``."""
    specs_missing_project = tuple(e for e in ENTITY_SPECS if e.name != "Project")
    with pytest.raises(RuntimeError, match="implies parent"):
        entity_build_order(specs_missing_project)
