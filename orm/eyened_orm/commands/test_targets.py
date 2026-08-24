"""Tests for shared eorm target selection."""

from __future__ import annotations

from datetime import datetime

import click
import pytest

from sqlalchemy import select

from eyened_orm import ImageInstance, Patient, Project
from eyened_orm.commands.targets import (
    TargetSpec,
    load_ids_from_file,
    resolve_image_target,
    resolve_patient_target,
    resolve_project,
    target_spec_from_cli,
)
from eyened_orm.importer.importer import plan_image_import
from eyened_orm.importer.importer_dtos import ImportRow
from eyened_orm.project import ExternalEnum


def _import_images(session, *, project_name: str = "target-proj", count: int = 2):
    defaults = {
        "project_external": "Y",
        "manufacturer": "m",
        "manufacturer_model_name": "mm",
        "device_description": "d",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    rows = [
        ImportRow(
            project_name=project_name,
            patient_identifier="pat-1",
            study_date=datetime(2026, 1, 1).date(),
            series_anonymous_identity=1,
            storage_backend_key=f"sb-{i}",
            object_key=f"img-{i}.png",
            modality="ColorFundus" if i == 0 else "OCT",
            laterality="L",
        )
        for i in range(count)
    ]
    run = plan_image_import(session, rows, defaults=defaults)
    run.apply()
    session.commit()
    proj = Project.by_name(session, project_name)
    images = session.scalars(select(ImageInstance)).all()
    return proj, images


def test_target_spec_from_cli_inline_ids():
    spec = target_spec_from_cli(image_ids="1,2,3")
    assert spec.image_ids == ["1", "2", "3"]


def test_resolve_image_target_inline_ids_and_public_ids(session):
    _proj, images = _import_images(session)
    spec = TargetSpec(
        image_ids=[
            str(images[0].ImageInstanceID),
            images[1].PublicID,
        ]
    )
    target = resolve_image_target(session, spec)
    assert target.image_ids == {images[0].ImageInstanceID, images[1].ImageInstanceID}


def test_resolve_project_by_name_and_id(session):
    proj = Project(ProjectName="named-proj", External=ExternalEnum.N, Description="")
    session.add(proj)
    session.commit()

    by_name = resolve_project(session, "named-proj")
    by_id = resolve_project(session, str(proj.ProjectID))
    assert by_name.ProjectID == proj.ProjectID
    assert by_id.ProjectName == "named-proj"


def test_resolve_image_target_from_file_with_public_id(session, tmp_path):
    proj, images = _import_images(session)
    path = tmp_path / "ids.txt"
    path.write_text(f"# comment\n{images[0].ImageInstanceID}\n{images[1].PublicID}\n")

    spec = TargetSpec(image_ids_file=str(path))
    target = resolve_image_target(session, spec)
    assert target.image_ids == {images[0].ImageInstanceID, images[1].ImageInstanceID}


def test_resolve_image_target_by_project_with_modality(session):
    proj, images = _import_images(session)
    spec = TargetSpec(project=str(proj.ProjectID), modality="ColorFundus")
    target = resolve_image_target(session, spec)
    cfi = next(im for im in images if im.Modality.name == "ColorFundus")
    assert target.image_ids == {cfi.ImageInstanceID}


def test_resolve_image_target_mutually_exclusive_path_and_project(session, tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text("1\n")
    spec = TargetSpec(image_ids_file=str(path), project="1")
    with pytest.raises(click.UsageError, match="mutually exclusive"):
        resolve_image_target(session, spec)


def test_resolve_patient_target_by_project(session):
    proj, _images = _import_images(session)
    pat = Patient.by_columns(session, ProjectID=proj.ProjectID)[0]
    spec = TargetSpec(project=str(proj.ProjectID))
    target = resolve_patient_target(session, spec)
    assert len(target.patients) == 1
    assert target.patients[0].PatientID == pat.PatientID


def test_resolve_patient_target_requires_project_when_ambiguous(session):
    proj_a = Project(ProjectName="proj-a", External=ExternalEnum.N, Description="")
    proj_b = Project(ProjectName="proj-b", External=ExternalEnum.N, Description="")
    session.add_all([proj_a, proj_b])
    session.flush()
    session.add_all(
        [
            Patient(PatientIdentifier="dup", ProjectID=proj_a.ProjectID),
            Patient(PatientIdentifier="dup", ProjectID=proj_b.ProjectID),
        ]
    )
    session.commit()

    spec = TargetSpec(patient="dup")
    with pytest.raises(click.UsageError, match="multiple projects"):
        resolve_patient_target(session, spec)


def test_resolve_patient_target_scoped_patient(session):
    proj, _images = _import_images(session)
    pat = Patient.by_columns(session, ProjectID=proj.ProjectID)[0]
    spec = TargetSpec(project=proj.ProjectName, patient="pat-1")
    target = resolve_patient_target(session, spec)
    assert len(target.patients) == 1
    assert target.patients[0].PatientID == pat.PatientID


def test_load_ids_from_file_skips_comments(session, tmp_path):
    _proj, images = _import_images(session, count=1)
    path = tmp_path / "ids.txt"
    path.write_text(f"\n# skip\n{images[0].ImageInstanceID}\n")
    ids = load_ids_from_file(session, str(path))
    assert ids == {images[0].ImageInstanceID}
