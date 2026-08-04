"""Every task->project operation: the classifying backfill and the two reports.

One module because the backfill and the operator reports share one query -- the
same four-join walk from a task's image links up to ``Patient.ProjectID``, which
is the schema's only project anchor.

Nothing here commits. These helpers flush; the CLI owns the transaction.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import column, func, select, table
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

# Core literals rather than ORM classes: this query runs under the SQLite test
# fixture and must stay independent of model changes.
_task = table("Task", column("TaskID"), column("TaskName"), column("ProjectID"))
_subtask = table("SubTask", column("SubTaskID"), column("TaskID"))
_link = table("SubTaskImageLink", column("SubTaskID"), column("ImageInstanceID"))
_image = table("ImageInstance", column("ImageInstanceID"), column("SeriesID"))
_series = table("Series", column("SeriesID"), column("StudyID"))
_study = table("Study", column("StudyID"), column("PatientID"))
_patient = table("Patient", column("PatientID"), column("ProjectID"))

SENTINEL_DESCRIPTION = (
    "Holding pen for legacy tasks whose project could not be determined from "
    "their images (they spanned several projects, or had no image evidence at "
    "all). This project has NO MEMBERS by design, so the tasks it holds are "
    "invisible to everyone.\n\n"
    "To make one reachable, an admin re-anchors it to a real project and grants "
    "the requesting user membership there:\n"
    "    eorm task-projects <TASKID> --for <username>\n"
    "    eorm grant-task-access <TASKID> --user <username> --role grader "
    "--anchor <PROJECTID>\n\n"
    "WARNING: deleting this project DELETES EVERY TASK IT HOLDS -- Task.ProjectID "
    "cascades."
)


def task_project_usage_rows() -> Select:
    """SELECT TaskID, ProjectID, subtasks, links -- one row per (task, project).

    Inactive images are counted deliberately: skipping them could make a task
    look like it has no image evidence at all.
    """
    return (
        select(
            _subtask.c.TaskID.label("task_id"),
            _patient.c.ProjectID.label("project_id"),
            func.count(func.distinct(_subtask.c.SubTaskID)).label("subtasks"),
            func.count().label("links"),
        )
        .select_from(_subtask)
        .join(_link, _link.c.SubTaskID == _subtask.c.SubTaskID)
        .join(_image, _image.c.ImageInstanceID == _link.c.ImageInstanceID)
        .join(_series, _series.c.SeriesID == _image.c.SeriesID)
        .join(_study, _study.c.StudyID == _series.c.StudyID)
        .join(_patient, _patient.c.PatientID == _study.c.PatientID)
        .group_by(_subtask.c.TaskID, _patient.c.ProjectID)
    )


@dataclass(frozen=True)
class BackfillPlan:
    """What the backfill would do. Produced read-only, applied separately."""

    anchored: dict[int, int]   # task_id -> the one project its images resolve to
    to_park: list[int]         # task ids with zero or several resolvable projects


@dataclass(frozen=True)
class BackfillReport:
    """What the backfill actually did."""

    anchored: int
    parked: int
    sentinel_project_id: int | None
    sentinel_created: bool

    @property
    def nothing_to_do(self) -> bool:
        return self.anchored == 0 and self.parked == 0


def classify(
    projects_by_task: dict[int, set[int]], task_ids: list[int]
) -> BackfillPlan:
    """The rule, as a pure function: no session, no database.

    A task whose image links all resolve to ONE project is anchored to it.
    Everything else -- ambiguous or evidence-free -- is parked. Nothing is
    guessed, so there is no tie-break rule.

    Public and separated from its I/O on purpose. This rule decides every
    anchor and can be silently wrong, so it is what the tests pin -- and it is
    the only half that *can* be pinned: ``Task.ProjectID`` is NOT NULL in the
    model, so the SQLite test schema (built by ``create_all``) cannot hold the
    un-anchored rows ``plan_backfill`` selects. That nullable window exists only
    between the two migration revisions, on a real database.
    """
    anchored: dict[int, int] = {}
    to_park: list[int] = []
    for task_id in task_ids:
        projects = projects_by_task.get(task_id, set())
        if len(projects) == 1:
            anchored[task_id] = next(iter(projects))
        else:
            to_park.append(task_id)
    return BackfillPlan(anchored=anchored, to_park=sorted(to_park))


def plan_backfill(session: Session) -> BackfillPlan:
    """Classify every task that has no project yet. Read-only.

    I/O only; the rule lives in ``classify``. The four-join walk this issues is
    covered by ``project_breakdown``'s tests, which exercise the same select
    against real image data.
    """
    projects_by_task: dict[int, set[int]] = {}
    for row in session.execute(task_project_usage_rows()):
        projects_by_task.setdefault(int(row.task_id), set()).add(int(row.project_id))

    unanchored = [
        int(task_id)
        for task_id in session.scalars(
            select(_task.c.TaskID).where(_task.c.ProjectID.is_(None))
        )
    ]
    return classify(projects_by_task, unanchored)


def apply_backfill(
    session: Session, plan: BackfillPlan, *, sentinel_name: str
) -> BackfillReport:
    """Write ``plan``. Flushes, never commits -- the CLI owns the transaction.

    Every write is ``WHERE ProjectID IS NULL``, so idempotency is structural and
    a re-run can never drag an already-anchored task back.

    ``sentinel_name`` is a parameter rather than a module constant on purpose:
    nothing outside the CLI that supplies it may resolve the sentinel.
    """
    anchored = 0
    for task_id, project_id in plan.anchored.items():
        result = session.execute(
            _task.update()
            .where(_task.c.TaskID == task_id, _task.c.ProjectID.is_(None))
            .values(ProjectID=project_id)
        )
        anchored += result.rowcount or 0

    sentinel_id: int | None = None
    sentinel_created = False
    parked = 0
    if plan.to_park:
        sentinel_id, sentinel_created = ensure_sentinel(session, sentinel_name)
        result = session.execute(
            _task.update()
            .where(_task.c.TaskID.in_(plan.to_park), _task.c.ProjectID.is_(None))
            .values(ProjectID=sentinel_id)
        )
        parked = result.rowcount or 0

    session.flush()
    return BackfillReport(
        anchored=anchored,
        parked=parked,
        sentinel_project_id=sentinel_id,
        sentinel_created=sentinel_created,
    )


@dataclass(frozen=True)
class ProjectUsage:
    """One project a task's images live in, with how much of the task is there."""

    project_id: int
    project_name: str
    subtasks: int
    links: int
    member: bool | None = None   # None when no user was named


@dataclass(frozen=True)
class TaskBreakdown:
    """Where a task's data lives, and where its anchor points."""

    task_id: int
    task_name: str
    anchor_project_id: int | None
    anchor_project_name: str | None
    parked: bool
    usage: list[ProjectUsage]


def project_breakdown(
    session: Session,
    task_id: int,
    *,
    sentinel_name: str,
    for_creator_id: int | None = None,
) -> TaskBreakdown:
    """Report the projects a task's images belong to. Read-only.

    ``parked`` is derived from the caller-supplied ``sentinel_name``, never from
    a constant this module owns.

    Raises:
        ValueError: If the task does not exist.
    """
    from eyened_orm import Project, ProjectMember, Task

    task = session.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")

    anchor_name = None
    if task.ProjectID is not None:
        anchor = session.get(Project, task.ProjectID)
        anchor_name = anchor.ProjectName if anchor is not None else None

    member_of: set[int] = set()
    if for_creator_id is not None:
        member_of = set(
            session.scalars(
                select(ProjectMember.ProjectID).where(
                    ProjectMember.CreatorID == for_creator_id
                )
            )
        )

    # WHERE, not HAVING: filtering before the group-by lets the planner use the
    # index on SubTask.TaskID instead of aggregating every task in the table
    # before discarding all but one row -- confirmed equivalent and cheaper by
    # running both against real seeded data.
    rows = session.execute(
        task_project_usage_rows().where(_subtask.c.TaskID == task_id)
    ).all()
    names = dict(
        session.execute(
            select(Project.ProjectID, Project.ProjectName).where(
                Project.ProjectID.in_([int(r.project_id) for r in rows] or [0])
            )
        ).all()
    )

    usage = sorted(
        (
            ProjectUsage(
                project_id=int(r.project_id),
                project_name=names.get(int(r.project_id), "?"),
                subtasks=int(r.subtasks),
                links=int(r.links),
                member=(int(r.project_id) in member_of)
                if for_creator_id is not None
                else None,
            )
            for r in rows
        ),
        key=lambda u: -u.subtasks,
    )

    return TaskBreakdown(
        task_id=task_id,
        task_name=task.TaskName,
        anchor_project_id=task.ProjectID,
        anchor_project_name=anchor_name,
        parked=anchor_name == sentinel_name,
        usage=usage,
    )


def ensure_sentinel(session: Session, sentinel_name: str) -> tuple[int, bool]:
    """Return (project_id, created). Minted only when something needs parking.

    Public because ``eorm grant-task-access --park`` needs the same row; the name
    still arrives as a parameter, never from a constant this module owns.
    """
    from eyened_orm import Project
    from eyened_orm.project import ExternalEnum

    existing = session.scalar(
        select(Project).where(Project.ProjectName == sentinel_name)
    )
    if existing is not None:
        return existing.ProjectID, False

    sentinel = Project(
        ProjectName=sentinel_name,
        External=ExternalEnum.N,
        Description=SENTINEL_DESCRIPTION,
    )
    session.add(sentinel)
    session.flush()
    return sentinel.ProjectID, True
