"""Declarations for imported tasks.

The task importer is a third writer of ``SubTaskImageLink`` -- alongside
``Task.create_from_imagesets`` and ``SubTaskRepository.add_link`` -- and the
one with real users. It builds rows generically through ``entity.model()``, so
it cannot be found by grepping for a constructor, and its entity graph
(``TASK_ENTITY_SPECS``) carries no project of its own: ``ImageInstanceID`` is a
flat field on the row, with no ``ImageInstance`` entity behind it.

So the declaration is resolved here, from ``ImageInstance.ProjectID`` -- one
indexed lookup per import, available since the column landed -- and the rule
mirrors ``create_from_imagesets`` exactly:

* a task this run **creates** declares the projects of the images it brings;
* a task that **already exists** is not extended. An image from an undeclared
  project is refused, because silently widening an existing task's declaration
  is the auto-extend the design rejects (section 2.1) -- it changes who can see
  work already recorded under the narrower declaration.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..image_instance import ImageInstance
from ..task import SubTaskImageLink, TaskProject
from .import_run import ImportCreate, ImportRun


def declare_task_projects(session: Session, run: ImportRun) -> None:
    """Append the ``TaskProject`` rows an import's links require.

    A no-op for image imports, which create no links.
    """
    created = {id(change.entity) for change in run.changes
               if isinstance(change, ImportCreate)}
    links = [
        change.entity
        for change in run.changes
        if isinstance(change, ImportCreate)
        and isinstance(change.entity, SubTaskImageLink)
    ]
    if not links:
        return

    image_ids = {link.ImageInstanceID for link in links}
    project_of = dict(
        session.execute(
            select(ImageInstance.ImageInstanceID, ImageInstance.ProjectID).where(
                ImageInstance.ImageInstanceID.in_(image_ids)
            )
        ).all()
    )
    # An image id with no row contributes no project, and is passed over rather
    # than refused. The link's own foreign key to ImageInstance is what rejects
    # a dangling id, when the run is applied -- which is where the importer has
    # always reported it and where its callers catch it. Refusing it here would
    # turn that IntegrityError into a ValueError raised out of ``plan_import``,
    # i.e. move the failure from the write to the plan.
    unresolved = image_ids - project_of.keys()

    # Keyed by identity: a task this run creates has no TaskID yet.
    tasks: dict[int, object] = {}
    wanted: dict[int, set[int]] = {}
    for link in links:
        if link.ImageInstanceID in unresolved:
            continue
        task = link.SubTask.Task
        tasks[id(task)] = task
        wanted.setdefault(id(task), set()).add(project_of[link.ImageInstanceID])

    # Collect every offender before raising: an import run is a batch, and an
    # operator with three mis-declared tasks should learn all three at once
    # rather than one re-run at a time.
    under_declared: list[str] = []
    for marker, projects in wanted.items():
        task = tasks[marker]
        if marker in created:
            for project_id in sorted(projects):
                run.add_create(TaskProject(Task=task, ProjectID=project_id), {})
            continue
        declared = set(
            session.scalars(
                select(TaskProject.ProjectID).where(TaskProject.TaskID == task.TaskID)
            )
        )
        outside = projects - declared
        if outside:
            under_declared.append(
                f"task {task.TaskID} ({task.TaskName!r}) does not declare "
                f"project(s) {sorted(outside)}; it declares {sorted(declared)}"
            )
    if under_declared:
        raise ValueError(
            "; ".join(under_declared)
            + ". Extend the task's declaration before importing images from "
            "those projects."
        )
