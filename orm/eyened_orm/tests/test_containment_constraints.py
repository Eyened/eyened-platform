"""Containment is a database constraint, not a convention."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from eyened_orm import ImageInstance, Patient, Series, Study
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
    """ON UPDATE CASCADE down all four levels, so no copy can go stale."""
    other = make_project(session, "C")
    ids = _chain_of(session, spanning["images"]["A"])
    session.get(Patient, ids["Patient"]).ProjectID = other.ProjectID
    session.flush()
    session.expunge_all()

    # Asserted level by level rather than on the image alone: a cascade that
    # stops part way down then names the level it stopped at, instead of
    # reporting only that the deepest copy is stale.
    assert session.get(Patient, ids["Patient"]).ProjectID == other.ProjectID
    assert session.get(Study, ids["Study"]).ProjectID == other.ProjectID
    assert session.get(Series, ids["Series"]).ProjectID == other.ProjectID
    assert (
        session.get(ImageInstance, ids["ImageInstance"]).ProjectID == other.ProjectID
    )


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
