"""Tests for the declaration cutover's pre-flight check.

Two properties matter here, and they fail in different directions. The queries
have to FIND a dangling row, and they have to be RUNNABLE on the schema that
exists before the chain applies -- which is not the schema these tests build,
because the models declare the post-migration shape. The compile guard at the
bottom covers the second, since no SQLite fixture can.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import pytest
from click.testing import CliRunner
from sqlalchemy import func, select
from sqlalchemy.dialects import mysql

from eyened_orm import SubTask, Task, TaskDefinition, TaskProject
from eyened_orm.commands import integrity as integrity_module
from eyened_orm.commands.integrity import (
    HOPS,
    check_dangling_references,
    dangling,
    dangling_references,
)
from eyened_orm.image_instance import ImageInstance
from eyened_orm.series import Series
from eyened_orm.task import SubTaskImageLink, SubTaskState, TaskState
from eyened_orm.utils.factories import (
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
)


@pytest.fixture()
def linked(session):
    """One well-formed row at every level, joined end to end by a task link."""
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project = make_project(session, "P")
    patient = make_patient(session, project, "pat")
    study = make_study(session, patient, date(2024, 1, 1))
    series = make_series(session, study)
    image = make_image(session, series, device, backend, "img")

    taskdef = TaskDefinition(TaskDefinitionName="def")
    session.add(taskdef)
    session.flush()
    task = Task(
        TaskName="t",
        TaskDefinitionID=taskdef.TaskDefinitionID,
        TaskState=TaskState.NotStarted,
    )
    session.add(task)
    session.flush()
    # Before the link, not after: the containment key rejects a link inserted
    # ahead of the declaration it needs.
    session.add(TaskProject(TaskID=task.TaskID, ProjectID=project.ProjectID))
    session.flush()
    subtask = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    session.add(subtask)
    session.flush()
    # TaskID and ProjectID are left unset on purpose: the unit of work fills
    # them from the composite keys during the flush, which is the write path
    # production uses.
    session.add(
        SubTaskImageLink(
            SubTaskID=subtask.SubTaskID,
            ImageInstanceID=image.ImageInstanceID,
            ImageIndex=0,
        )
    )
    session.commit()
    return {
        "patient": patient.PatientID,
        "study": study.StudyID,
        "series": series.SeriesID,
        "image": image.ImageInstanceID,
        "subtask": subtask.SubTaskID,
    }


def _orphan(session, engine, table: str, pk_column: str, value: int) -> None:
    """Delete a parent the way a dump restore does -- with the keys not looking.

    Enforced, every hop's key is ON DELETE CASCADE and the delete would take
    the child with it. SQLite also ignores ``PRAGMA foreign_keys`` issued
    inside a transaction, so the commit and the separate connection are both
    load-bearing rather than tidiness.
    """
    session.commit()
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql(f"DELETE FROM {table} WHERE {pk_column} = ?", (value,))
        conn.commit()
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    session.expire_all()


def test_orphaning_a_parent_leaves_the_child_behind(session, engine, linked):
    """Positive control for every test below that orphans a row.

    If the PRAGMA does not take, the cascade removes the child instead and the
    dangling assertions all run against a database with nothing dangling in it.
    This says which of the two happened.
    """
    before = session.scalar(select(func.count()).select_from(ImageInstance))
    _orphan(session, engine, "Series", "SeriesID", linked["series"])
    assert session.scalar(select(func.count()).select_from(ImageInstance)) == before


def test_a_well_formed_chain_has_nothing_dangling(session, linked):
    """The expected result on any database written only through the app."""
    results = dangling_references(session)
    assert len(results) == len(HOPS)
    assert [result.count for result in results] == [0] * len(HOPS)
    assert all(result.sample == () for result in results)


# Deleting each parent dangles exactly one hop, and the id the report should
# name is the child's own identifying column -- not the parent's.
_ORPHANINGS = (
    ("Series", "SeriesID", "series", "ImageInstance", "Series", "image"),
    ("Study", "StudyID", "study", "Series", "Study", "series"),
    ("Patient", "PatientID", "patient", "Study", "Patient", "study"),
    ("SubTask", "SubTaskID", "subtask", "SubTaskImageLink", "SubTask", "subtask"),
    (
        "ImageInstance",
        "ImageInstanceID",
        "image",
        "SubTaskImageLink",
        "ImageInstance",
        "image",
    ),
)


@pytest.mark.parametrize(
    "table, pk_column, deleted, child, parent, reported",
    _ORPHANINGS,
    ids=[f"{row[3]}->{row[4]}" for row in _ORPHANINGS],
)
def test_each_hop_reports_the_row_whose_backfill_would_be_null(
    session, engine, linked, table, pk_column, deleted, child, parent, reported
):
    """One missing parent, found by its own hop and by no other."""
    _orphan(session, engine, table, pk_column, linked[deleted])

    results = {(r.hop.child, r.hop.parent): r for r in dangling_references(session)}
    assert [key for key, r in results.items() if r.count] == [(child, parent)]

    found = results[(child, parent)]
    assert found.count == 1
    assert found.sample == (linked[reported],)


def test_the_sample_is_bounded_and_the_count_is_not(session, engine, linked):
    """A restore that lost a whole table should not print a line per row."""
    backend = make_storage_backend(session, "b2")
    device = make_device(session, "d2")
    series = session.get(Series, linked["series"])
    for n in range(3):
        make_image(session, series, device, backend, f"extra-{n}")
    session.commit()

    _orphan(session, engine, "Series", "SeriesID", linked["series"])

    (found,) = [r for r in dangling_references(session, sample_size=2) if r.count]
    assert found.count == 4
    assert len(found.sample) == 2


def test_asking_for_no_ids_still_reports_the_count(session, engine, linked):
    """`--sample 0` must not read as a clean database."""
    _orphan(session, engine, "Series", "SeriesID", linked["series"])
    (found,) = [r for r in dangling_references(session, sample_size=0) if r.count]
    assert found.count == 1
    assert found.sample == ()


# The columns and table the five migrations add, as they appear once compiled.
# Qualified, not bare names: `SubTaskID` contains `TaskID`, so a substring ban
# on the bare column would fail every hop that reports a subtask id.
_ADDED_BY_THE_CHAIN = (
    "`ImageInstance`.`ProjectID`",
    "`Study`.`ProjectID`",
    "`Series`.`ProjectID`",
    "`SubTaskImageLink`.`TaskID`",
    "`SubTaskImageLink`.`ProjectID`",
    "`TaskProject`",
)


@pytest.mark.parametrize("hop", HOPS, ids=[f"{h.child}->{h.parent}" for h in HOPS])
def test_no_hop_references_a_column_the_chain_adds(hop):
    """The pre-flight runs before the migrations, so it may only name columns
    that already exist. This is what forces the explicit ON clauses."""
    sql = str(dangling(hop).compile(dialect=mysql.dialect()))
    for token in _ADDED_BY_THE_CHAIN:
        assert token not in sql, f"{hop.child} -> {hop.parent} emitted: {sql}"


def test_the_relationship_join_would_have_emitted_them():
    """Positive control for the guard above.

    `SubTaskImageLink.SubTask` now resolves through the composite key
    (SubTaskID, TaskID), so joining through the relationship -- the obvious way
    to write this -- puts a column the target database does not have into the
    predicate. The guard is refusing something reachable, not something
    hypothetical.
    """
    sql = str(
        select(SubTaskImageLink.SubTaskID)
        .outerjoin(SubTaskImageLink.SubTask)
        .compile(dialect=mysql.dialect())
    )
    assert "`SubTaskImageLink`.`TaskID`" in sql


@pytest.fixture()
def stub_database(session, monkeypatch):
    """Hand the command the in-memory test session instead of a real Database()."""

    class _FakeDatabase:
        @contextmanager
        def get_session(self):
            try:
                yield session  # deliberately not closed: the test reads after
            finally:
                session.rollback()

    monkeypatch.setattr(integrity_module, "get_database", lambda: _FakeDatabase())


def test_the_shell_reports_a_clean_database_and_says_how_much_it_looked_at(
    linked, stub_database
):
    result = CliRunner().invoke(check_dangling_references, [])
    assert result.exit_code == 0
    assert result.output.strip() == "No dangling references (5 hops checked)."


def test_the_shell_names_the_hop_the_column_and_the_ids(session, engine, linked, stub_database):
    _orphan(session, engine, "Series", "SeriesID", linked["series"])

    result = CliRunner().invoke(check_dangling_references, [])
    assert result.exit_code == 0, result.output
    assert "ImageInstance -> Series: 1 row(s) with no parent" in result.output
    assert "ImageInstance.ProjectID would backfill to NULL" in result.output
    assert f"ImageInstanceID: {linked['image']}" in result.output
    assert "more)" not in result.output


def test_the_shell_says_how_many_ids_it_withheld(session, engine, linked, stub_database):
    """The count is the total; the sample is what fits. The arithmetic between
    them is the only place this command can lie to an operator."""
    backend = make_storage_backend(session, "b2")
    device = make_device(session, "d2")
    series = session.get(Series, linked["series"])
    for n in range(3):
        make_image(session, series, device, backend, f"extra-{n}")
    session.commit()
    _orphan(session, engine, "Series", "SeriesID", linked["series"])

    result = CliRunner().invoke(check_dangling_references, ["--sample", "2"])
    assert result.exit_code == 0, result.output
    assert "4 row(s) with no parent" in result.output
    assert "(+2 more)" in result.output


def test_the_shell_still_exits_zero_when_it_finds_something(
    session, engine, linked, stub_database
):
    """A report, not a gate: the decision stays with the operator."""
    _orphan(session, engine, "SubTask", "SubTaskID", linked["subtask"])
    result = CliRunner().invoke(check_dangling_references, [])
    assert result.exit_code == 0
    assert "SubTaskImageLink -> SubTask" in result.output
