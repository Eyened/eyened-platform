"""The classifying backfill: anchor what is provable, park the rest.

⚠️ **No test here seeds a NULL ``Task.ProjectID``, and none can.** The model
declares it NOT NULL and ``sqlite_testdb`` builds the schema with ``create_all``,
so an un-anchored row is unrepresentable in tests -- that state exists only
between the two migration revisions on a real database. The rule is therefore
pinned through ``classify``, which is pure, and ``apply_backfill``'s
``WHERE ProjectID IS NULL`` guard is pinned by showing it decline to write.
"""
from sqlalchemy import func, select

from eyened_orm import Project, Task, TaskDefinition
from eyened_orm.task import TaskState
from eyened_orm.utils.factories import make_project
from eyened_orm.utils.task_projects import BackfillPlan, apply_backfill, classify

SENTINEL = "_test_sentinel"


def _task(session, name: str, project_id: int) -> Task:
    td = session.scalar(
        select(TaskDefinition).where(TaskDefinition.TaskDefinitionName == "td")
    )
    if td is None:
        td = TaskDefinition(TaskDefinitionName="td")
        session.add(td)
        session.flush()
    task = Task(
        TaskName=name,
        TaskDefinitionID=td.TaskDefinitionID,
        TaskState=TaskState.NotStarted,
        ProjectID=project_id,
    )
    session.add(task)
    session.flush()
    return task


def test_classify_anchors_a_task_whose_images_prove_one_project():
    """One resolvable project is the whole condition for anchoring."""
    plan = classify({7: {11}}, [7])

    assert plan.anchored == {7: 11}
    assert plan.to_park == []


def test_classify_parks_an_ambiguous_task():
    """Two projects is not a tie to break -- it is simply unresolvable."""
    plan = classify({7: {11, 12}}, [7])

    assert plan.anchored == {}
    assert plan.to_park == [7]


def test_classify_parks_a_task_with_no_image_evidence():
    """A task absent from the usage rows has no images at all, so it parks too."""
    plan = classify({}, [7])

    assert plan.anchored == {}
    assert plan.to_park == [7]


def test_apply_backfill_mints_no_sentinel_when_nothing_needs_parking(session):
    """The sentinel is minted lazily -- a clean deployment never grows one."""
    report = apply_backfill(
        session, BackfillPlan(anchored={}, to_park=[]), sentinel_name=SENTINEL
    )

    assert session.scalar(select(Project).where(Project.ProjectName == SENTINEL)) is None
    assert report.sentinel_project_id is None
    assert report.sentinel_created is False
    assert report.nothing_to_do is True


def test_apply_backfill_never_overwrites_a_task_that_has_a_project(session):
    """Every write is WHERE ProjectID IS NULL, so a re-run can never drag an
    already-anchored task back -- not even one the plan names."""
    kept = make_project(session, "P-kept")
    other = make_project(session, "P-other")
    task = _task(session, "already", kept.ProjectID)

    # A plan that explicitly names this task, for both destinations.
    report = apply_backfill(
        session,
        BackfillPlan(anchored={task.TaskID: other.ProjectID}, to_park=[task.TaskID]),
        sentinel_name=SENTINEL,
    )

    assert session.get(Task, task.TaskID).ProjectID == kept.ProjectID
    assert report.anchored == 0
    assert report.parked == 0


def test_apply_backfill_reuses_an_existing_sentinel_on_a_second_run(session):
    """Idempotency is structural: the sentinel is found, not minted twice."""
    plan = BackfillPlan(anchored={}, to_park=[1])
    first = apply_backfill(session, plan, sentinel_name=SENTINEL)

    second = apply_backfill(session, plan, sentinel_name=SENTINEL)

    assert first.sentinel_created is True
    assert second.sentinel_created is False
    assert second.sentinel_project_id == first.sentinel_project_id
    assert (
        session.scalar(
            select(func.count()).select_from(Project).where(
                Project.ProjectName == SENTINEL
            )
        )
        == 1
    )
