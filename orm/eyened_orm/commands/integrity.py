"""Pre-flight integrity checks for the task-project declaration cutover.

The declaration chain adds five NOT NULL columns and backfills each from a
parent row reached by a join. A child whose parent row is missing backfills to
NULL, and the ``MODIFY ... NOT NULL`` that follows dies with ``ERROR 1138
Invalid use of NULL value`` -- naming no table, no column and no row, partway
into a maintenance window, with the schema half changed.

This reports that class of row before the window opens, so the decision is made
with the site still up.

Expect it to be clean. Every hop below already carries an enforced foreign key
with ``ON DELETE CASCADE`` in the pre-migration schema, so ordinary writes
cannot dangle a child and deleting a parent removes the child rather than
orphaning it. The one route that stays open is a load with checks off --
``mysqldump`` output sets ``FOREIGN_KEY_CHECKS=0`` so tables can arrive in any
order, and a row that violates a key loads silently and stays. A database that
has only ever been written through the application has nothing here; a restored
one is the reason to look.

Runs against the schema as it stands BEFORE the chain applies. That is the
constraint every query here is written to: it may reference only columns that
exist on both sides of the migration, which is why the joins are spelled out
rather than taken from the mapped relationships. ``SubTaskImageLink.SubTask``
and ``.ImageInstance`` now resolve through the composite keys
``(SubTaskID, TaskID)`` and ``(ImageInstanceID, ProjectID)``, so joining through
either would emit a predicate on a column the target database does not have yet,
and the check would fail on precisely the database it exists to check.
"""
from __future__ import annotations

from dataclasses import dataclass

import click
from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from ..image_instance import ImageInstance
from ..patient import Patient
from ..series import Series
from ..study import Study
from ..task import SubTask, SubTaskImageLink
from .shared import get_database


@dataclass(frozen=True)
class Hop:
    """One parent lookup a backfill depends on."""

    child_id: InstrumentedAttribute
    child_fk: InstrumentedAttribute
    parent_pk: InstrumentedAttribute
    # The NOT NULL column the chain adds that this hop feeds. Carried so the
    # report can say which migration a dangling row would stop, rather than
    # leaving the operator to work it out from the table names.
    backfills: str

    @property
    def child(self) -> str:
        return self.child_id.parent.entity.__name__

    @property
    def parent(self) -> str:
        return self.parent_pk.parent.entity.__name__

    @property
    def key(self) -> str:
        return self.child_id.key


# In chain order: the three patient-chain hops feed d3ce100ab2b6 and
# 4eae42457fa2, the two link hops feed 2db0e63195db.
#
# Patient.ProjectID is not a hop. It is already NOT NULL in the pre-migration
# schema, so a Patient that exists always carries a project; only a missing
# Patient can make the walk resolve to nothing, and Study -> Patient covers
# that.
HOPS: tuple[Hop, ...] = (
    Hop(
        child_id=ImageInstance.ImageInstanceID,
        child_fk=ImageInstance.SeriesID,
        parent_pk=Series.SeriesID,
        backfills="ImageInstance.ProjectID",
    ),
    Hop(
        child_id=Series.SeriesID,
        child_fk=Series.StudyID,
        parent_pk=Study.StudyID,
        backfills="Series.ProjectID",
    ),
    Hop(
        child_id=Study.StudyID,
        child_fk=Study.PatientID,
        parent_pk=Patient.PatientID,
        backfills="Study.ProjectID",
    ),
    Hop(
        child_id=SubTaskImageLink.SubTaskID,
        child_fk=SubTaskImageLink.SubTaskID,
        parent_pk=SubTask.SubTaskID,
        backfills="SubTaskImageLink.TaskID",
    ),
    Hop(
        child_id=SubTaskImageLink.ImageInstanceID,
        child_fk=SubTaskImageLink.ImageInstanceID,
        parent_pk=ImageInstance.ImageInstanceID,
        backfills="SubTaskImageLink.ProjectID",
    ),
)


@dataclass(frozen=True)
class HopResult:
    hop: Hop
    count: int
    # Bounded: a restore that lost a whole table would otherwise print a line
    # per row. Enough to start diagnosing, and `count` says how much is behind
    # it.
    sample: tuple[int, ...]


def dangling(hop: Hop):
    """Rows whose parent is gone, as a SELECT of the child's identifying column.

    An anti-join rather than ``NOT IN``: the child columns are all NOT NULL
    here, so the two agree, but ``NOT IN`` against a NULL-bearing subquery
    returns nothing at all, and that is a failure mode worth not inheriting if
    a hop is ever added on a nullable column.
    """
    return (
        select(hop.child_id)
        .outerjoin(hop.parent_pk.parent.entity, hop.child_fk == hop.parent_pk)
        .where(hop.parent_pk.is_(None))
    )


def dangling_references(
    session: Session, *, sample_size: int = 20
) -> list[HopResult]:
    """Check every hop, returning one result each -- clean hops included.

    Clean hops are reported rather than dropped so a caller can say how much
    was covered. A green run means the whole set was looked at, not that the
    loop happened to find nothing.
    """
    results = []
    for hop in HOPS:
        # A one-row probe decides whether to ask anything else. On a clean
        # database -- the expected case, every time -- that is the only
        # statement this hop runs, and it stops at the first row rather than
        # counting to zero. The probe is deliberately independent of
        # `sample_size`: driving it from that would make `--sample 0` report
        # every hop clean instead of reporting counts with no ids.
        if session.scalar(dangling(hop).limit(1)) is None:
            results.append(HopResult(hop=hop, count=0, sample=()))
            continue
        count = session.scalar(
            select(func.count()).select_from(dangling(hop).subquery())
        )
        sample = tuple(session.scalars(dangling(hop).limit(sample_size)))
        results.append(HopResult(hop=hop, count=count, sample=sample))
    return results


@click.command("check-dangling-references")
@click.option(
    "--sample",
    type=int,
    default=20,
    show_default=True,
    help="How many offending ids to print per hop.",
)
def check_dangling_references(sample: int) -> None:
    """Report rows whose parent is missing, before the declaration cutover.

    Read-only, and a report rather than a gate: it always exits 0. What to do
    about a dangling row is a judgement the operator makes with the rest of the
    cutover in view, not something this command should decide by its exit code.
    """
    database = get_database()
    with database.get_session() as session:
        results = dangling_references(session, sample_size=sample)

    broken = [result for result in results if result.count]
    if not broken:
        click.echo(f"No dangling references ({len(results)} hops checked).")
        return

    for result in broken:
        hop = result.hop
        click.echo(
            f"{hop.child} -> {hop.parent}: {result.count} row(s) with no parent; "
            f"{hop.backfills} would backfill to NULL and fail its NOT NULL."
        )
        shown = ", ".join(str(value) for value in result.sample)
        remaining = result.count - len(result.sample)
        suffix = f" (+{remaining} more)" if remaining > 0 else ""
        click.echo(f"    {hop.key}: {shown}{suffix}")


integrity_commands = [check_dangling_references]
