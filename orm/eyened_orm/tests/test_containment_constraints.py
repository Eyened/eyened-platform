"""Containment is a database constraint, not a convention."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from eyened_orm import ImageInstance, Patient, Series, Study, TaskProject
from eyened_orm.utils.factories import make_project

# (table, primary key column) for each level that carries a derived ProjectID,
# parent first. The ids are read off the object graph rather than listed,
# because `spanning` only hands back the image.
_CHAIN = (("Study", "StudyID"), ("Series", "SeriesID"),
          ("ImageInstance", "ImageInstanceID"))


def _chain_of(session, image_id: int) -> dict[str, int]:
    """Primary keys of the Patient -> ImageInstance chain holding `image_id`."""
    image = session.get(ImageInstance, image_id)
    return {
        "Patient": image.Series.Study.PatientID,
        "Study": image.Series.StudyID,
        "Series": image.SeriesID,
        "ImageInstance": image.ImageInstanceID,
    }


def test_moving_a_patient_carries_its_whole_chain(session, spanning):
    """ON UPDATE CASCADE down all five levels, so no copy can go stale.

    Image A is linked by BOTH the spanning task and the a_only task, so both
    must declare the destination before the move is legal: a patient's project
    cannot move out from under a task that has not agreed to it. Without those
    two declarations this is
    `test_moving_a_patient_into_an_undeclared_project_is_refused`.
    """
    other = make_project(session, "C")
    # Captured before anything detaches `other`, per the suite's
    # expire_on_commit=True convention.
    other_id = other.ProjectID
    for task_id in (spanning["task"], spanning["a_only"]):
        session.add(TaskProject(TaskID=task_id, ProjectID=other_id))
    session.flush()

    ids = _chain_of(session, spanning["images"]["A"])
    session.get(Patient, ids["Patient"]).ProjectID = other_id
    session.flush()
    session.expunge_all()

    # Asserted level by level rather than on the image alone: a cascade that
    # stops part way down then names the level it stopped at, instead of
    # reporting only that the deepest copy is stale.
    assert session.get(Patient, ids["Patient"]).ProjectID == other_id
    assert session.get(Study, ids["Study"]).ProjectID == other_id
    assert session.get(Series, ids["Series"]).ProjectID == other_id
    assert session.get(ImageInstance, ids["ImageInstance"]).ProjectID == other_id
    # The fifth level: SubTaskImageLink carries its own copy, and only
    # fk_SubTaskImageLink_Image_Project's ON UPDATE CASCADE keeps it in step.
    assert session.execute(
        text(
            "SELECT DISTINCT ProjectID FROM SubTaskImageLink "
            "WHERE ImageInstanceID = :id"
        ),
        {"id": ids["ImageInstance"]},
    ).scalars().all() == [other_id]


@pytest.mark.parametrize(("table", "pk_column"), _CHAIN)
def test_a_child_cannot_be_moved_out_of_its_parents_project(
    session, spanning, table, pk_column
):
    """The refusal direction: no row may claim a project its parent is not in.

    Written in SQL on purpose. Through the ORM the listeners in
    authz/denormalization and SQLAlchemy's own foreign-key sync would supply
    the right value before the constraint ever saw the wrong one, so an ORM
    test here would pass whether or not the constraint exists.
    """
    other = make_project(session, "C")
    ids = _chain_of(session, spanning["images"]["A"])

    with pytest.raises(IntegrityError):
        session.execute(
            text(f"UPDATE {table} SET ProjectID = :p WHERE {pk_column} = :id"),
            {"p": other.ProjectID, "id": ids[table]},
        )
    session.rollback()

    # Refused, not merely reported: the row still holds the project it had.
    assert session.execute(
        text(f"SELECT ProjectID FROM {table} WHERE {pk_column} = :id"),
        {"id": ids[table]},
    ).scalar() == spanning["projects"]["A"]


def test_deleting_a_patient_still_takes_its_chain_with_it(session, spanning):
    """ON DELETE CASCADE survived being folded into the composite keys.

    The composite keys replaced single-column ones that already cascaded on
    delete, and carrying that across is easy to drop silently: nothing else in
    the suite deletes a Patient.

    In SQL for the same reason as the refusal test, and preceded by two
    unrelated deletes: ImageStorage and SubTaskImageLink reach into the chain
    by keys of their own that this task never touched, and both default to NO
    ACTION, so leaving them would fail the DELETE for a reason that says
    nothing about the keys under test.
    """
    kept = _chain_of(session, spanning["images"]["B"])
    doomed = _chain_of(session, spanning["images"]["A"])
    session.execute(text("DELETE FROM SubTaskImageLink"))
    session.execute(text("DELETE FROM ImageStorage"))

    session.execute(
        text("DELETE FROM Patient WHERE PatientID = :id"),
        {"id": doomed["Patient"]},
    )

    for table, pk_column in _CHAIN:
        assert session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {pk_column} = :id"),
            {"id": doomed[table]},
        ).scalar() == 0, f"{table} row outlived its Patient"
        # The cascade followed the chain rather than emptying the table.
        assert session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {pk_column} = :id"),
            {"id": kept[table]},
        ).scalar() == 1, f"{table} lost a row belonging to another Patient"


def test_an_undeclared_image_cannot_be_linked(session, spanning):
    """The whole design in one assertion."""
    from eyened_orm import SubTaskImageLink

    session.add(
        SubTaskImageLink(
            SubTaskID=spanning["subtasks"]["a_only-A"],
            ImageInstanceID=spanning["images"]["B"],
            ImageIndex=99,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_declaration_in_use_cannot_be_removed(session, spanning):
    """Shrinking below what the links need would be fail-open."""
    declared = session.get(
        TaskProject,
        {"TaskID": spanning["task"], "ProjectID": spanning["projects"]["A"]},
    )
    assert declared is not None, "Task 4 should have made the fixture declare this"
    session.delete(declared)
    with pytest.raises(IntegrityError):
        session.flush()


def test_moving_a_patient_into_an_undeclared_project_is_refused(session, spanning):
    """The refusal fires at the far end of a four-level cascade."""
    other = make_project(session, "C")
    patient = session.get(ImageInstance, spanning["images"]["A"]).Series.Study.Patient
    patient.ProjectID = other.ProjectID
    with pytest.raises(IntegrityError):
        session.flush()
