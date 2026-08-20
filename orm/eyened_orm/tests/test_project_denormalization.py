"""Derived ProjectID columns are populated on insert, from the parent row."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import literal, select

from eyened_orm import ImageInstance, Patient, Project, Series, Study
from eyened_orm.project import ExternalEnum
from eyened_orm.utils.factories import (
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
)


def test_image_inherits_its_patients_project(session):
    """Raw-id writer: the factories set SeriesID, never the relationship."""
    project = make_project(session, "P")
    project_id = project.ProjectID  # capture BEFORE commit()
    patient = make_patient(session, project, "pat")
    series = make_series(session, make_study(session, patient, date(2024, 1, 1)))
    image = make_image(
        session, series, make_device(session, "d"), make_storage_backend(session), "img"
    )
    session.commit()
    image_id = image.ImageInstanceID
    session.expunge_all()
    assert session.get(ImageInstance, image_id).ProjectID == project_id


def test_a_pending_hierarchy_resolves_through_the_object_graph(session):
    """The importer's shape: parents assigned by relationship, nothing flushed.

    The factories flush after every add, so they cannot build this case -- and
    it is the one a database lookup cannot serve, because the parent rows do
    not exist yet.
    """
    project = make_project(session, "P2")
    device = make_device(session, "d2")
    patient = Patient(PatientIdentifier="pat-pending", ProjectID=project.ProjectID)
    study = Study(Patient=patient, StudyDate=date(2024, 1, 2))
    series = Series(Study=study)
    image = ImageInstance(
        Series=series,
        PublicID="img-pending",
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier="ds-pending",
        Rows_y=4,
        Columns_x=4,
    )
    session.add(image)
    session.flush()
    assert image.ProjectID == project.ProjectID


def test_a_pending_project_resolves_at_insert_time(session):
    """The importer's real shape: even the Project has no primary key yet.

    Nothing upstream can be read at before_flush -- the project's id does not
    exist until its own INSERT -- so this is what the before_insert backstop is
    for.
    """
    device = make_device(session, "d3")
    project = Project(ProjectName="P3", External=ExternalEnum.N)
    patient = Patient(PatientIdentifier="pat-all-pending", Project=project)
    study = Study(Patient=patient, StudyDate=date(2024, 1, 3))
    series = Series(Study=study)
    image = ImageInstance(
        Series=series,
        PublicID="img-all-pending",
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier="ds-all-pending",
        Rows_y=4,
        Columns_x=4,
    )
    session.add(image)
    session.commit()
    image_id, project_id = image.ImageInstanceID, project.ProjectID
    session.expunge_all()
    assert session.get(ImageInstance, image_id).ProjectID == project_id


def test_an_unreachable_parent_names_the_hop_that_dead_ended(session):
    """A raw SeriesID pointing at no row fails legibly, not as a NOT NULL error."""
    device = make_device(session, "d4")
    image = ImageInstance(
        SeriesID=9999,
        PublicID="img-orphan",
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier="ds-orphan",
        Rows_y=4,
        Columns_x=4,
    )
    session.add(image)
    with pytest.raises(ValueError, match=r"ImageInstance.Series is unset"):
        session.flush()


def test_a_parent_id_that_reaches_no_row_is_not_deferred(session):
    """The dead end is raised at before_flush, so no INSERT is ever emitted."""
    device = make_device(session, "d5")
    image = ImageInstance(
        SeriesID=9998,
        PublicID="img-dead-parent",
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier="ds-dead-parent",
        Rows_y=4,
        Columns_x=4,
    )
    session.add(image)
    with pytest.raises(ValueError, match=r"SeriesID=9998 reaches no Series row"):
        session.flush()
    # Deferring to before_insert would have raised mid-flush, after the
    # ancestors' INSERTs, leaving the session in PendingRollbackError.
    assert session.execute(select(literal(1))).scalar() == 1


def test_study_and_series_inherit_the_project(session):
    """The whole chain is populated whichever writer built it."""
    project = make_project(session, "P6")
    project_id = project.ProjectID  # capture BEFORE commit()
    patient = make_patient(session, project, "pat-chain")
    study = make_study(session, patient, date(2024, 1, 6))
    series = make_series(session, study)
    session.commit()
    study_id, series_id = study.StudyID, series.SeriesID
    session.expunge_all()
    assert session.get(Study, study_id).ProjectID == project_id
    assert session.get(Series, series_id).ProjectID == project_id


def test_a_pending_chain_reaches_study_and_series_at_insert_time(session):
    """The Study/Series backstop, with no ImageInstance to carry it.

    Nothing upstream is readable at before_flush -- the project's id does not
    exist until its own INSERT -- so if before_insert were still attached to
    ImageInstance alone, both columns would arrive at their INSERTs unset.
    """
    project = Project(ProjectName="P7", External=ExternalEnum.N)
    patient = Patient(PatientIdentifier="pat-chain-pending", Project=project)
    study = Study(Patient=patient, StudyDate=date(2024, 1, 7))
    series = Series(Study=study)
    session.add(series)
    session.commit()
    study_id, series_id, project_id = study.StudyID, series.SeriesID, project.ProjectID
    session.expunge_all()
    assert session.get(Study, study_id).ProjectID == project_id
    assert session.get(Series, series_id).ProjectID == project_id
