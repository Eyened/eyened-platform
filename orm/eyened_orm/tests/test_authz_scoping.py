"""One project-resolution rule per entity, shared by reads, writes and the CLI."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import sqlite

from eyened_orm import (
    FormAnnotation,
    ImageInstance,
    ModelSegmentation,
    Patient,
    Series,
    Study,
    SubTask,
    Task,
    TaskProject,
)
from eyened_orm.authz import scoping
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope
from eyened_orm.authz.scoping import (
    SET_VALUED_ENTITIES,
    SINGLE_PROJECT_ENTITIES,
    _ONE_HOP_TO,
    apply_scope,
    image_project_pairs,
    projects_of,
    scope_criteria,
)
from eyened_orm.task import SubTaskState, TaskState
from eyened_orm.utils.factories import (
    make_creator,
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
)


def _image_in(session, project_name, public_id, backend, device):
    project = make_project(session, project_name)
    patient = make_patient(session, project, f"pat-{project_name}")
    study = make_study(session, patient, date(2024, 1, 1))
    series = make_series(session, study)
    image = make_image(session, series, device, backend, public_id)
    return project, image


def _task_over(session, images, *, name="T"):
    from eyened_orm import TaskDefinition

    images = list(images)
    taskdef = TaskDefinition(TaskDefinitionName=f"def-{name}")
    session.add(taskdef)
    session.flush()
    task = Task(TaskName=name, TaskDefinitionID=taskdef.TaskDefinitionID,
                TaskState=TaskState.NotStarted)
    session.add(task)
    session.flush()
    subtask = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    session.add(subtask)
    session.flush()
    from eyened_orm import SubTaskImageLink, TaskProject

    # Declared before the links: the containment foreign key checks the
    # declaration at the moment a link is inserted. An empty ``images``
    # declares nothing, which is the no-images case one caller relies on.
    for project_id in sorted({image.ProjectID for image in images}):
        session.add(TaskProject(TaskID=task.TaskID, ProjectID=project_id))
    session.flush()
    for index, image in enumerate(images):
        session.add(
            SubTaskImageLink(
                SubTaskID=subtask.SubTaskID,
                ImageInstanceID=image.ImageInstanceID,
                ImageIndex=index,
            )
        )
    session.flush()
    return task, subtask


def test_an_image_resolves_to_its_patients_project(session):
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project, image = _image_in(session, "A", "img-a", backend, device)
    # A second project + patient, so a resolver that returned *every* project in
    # the database would fail this assertion instead of passing it.
    make_patient(session, make_project(session, "B"), "pat-B")
    session.commit()
    assert projects_of(session, ImageInstance, image.ImageInstanceID) == {
        project.ProjectID
    }


def test_a_task_resolves_to_every_project_its_images_touch(session):
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)
    project_b, image_b = _image_in(session, "B", "img-b", backend, device)
    task, _ = _task_over(session, [image_a, image_b])
    session.commit()
    assert projects_of(session, Task, task.TaskID) == {
        project_a.ProjectID,
        project_b.ProjectID,
    }


def test_a_subtask_resolves_to_its_parent_tasks_projects(session):
    """A superset of its own images: you see a whole task or none of it.

    v0.3 can be read both ways -- its Visibility table says a subtask's projects
    are "the projects of its images", consequence 1 says a user missing any of a
    task's projects sees no part of it. The stricter reading wins, per v0.3's
    own tie-breaker: prefer the rule that can be tightened later without
    withdrawing something users already have.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)
    project_b, image_b = _image_in(session, "B", "img-b", backend, device)

    from eyened_orm import SubTaskImageLink, TaskDefinition, TaskProject

    taskdef = TaskDefinition(TaskDefinitionName="def")
    session.add(taskdef)
    session.flush()
    task = Task(TaskName="T", TaskDefinitionID=taskdef.TaskDefinitionID,
                TaskState=TaskState.NotStarted)
    session.add(task)
    session.flush()
    only_a = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    only_b = SubTask(TaskID=task.TaskID, TaskState=SubTaskState.NotStarted)
    session.add_all([only_a, only_b])
    session.flush()
    # Declared before the links: the containment foreign key checks the
    # declaration at the moment a link is inserted, and this task spans both.
    session.add_all([
        TaskProject(TaskID=task.TaskID, ProjectID=project_a.ProjectID),
        TaskProject(TaskID=task.TaskID, ProjectID=project_b.ProjectID),
    ])
    session.flush()
    session.add_all([
        SubTaskImageLink(SubTaskID=only_a.SubTaskID,
                         ImageInstanceID=image_a.ImageInstanceID, ImageIndex=0),
        SubTaskImageLink(SubTaskID=only_b.SubTaskID,
                         ImageInstanceID=image_b.ImageInstanceID, ImageIndex=0),
    ])
    session.commit()

    both = {project_a.ProjectID, project_b.ProjectID}
    assert projects_of(session, SubTask, only_a.SubTaskID) == both
    assert projects_of(session, SubTask, only_b.SubTaskID) == both


def test_an_inactive_image_still_ties_its_project_to_the_task(session):
    """Excluding soft-deleted images would silently *widen* who sees the task.

    No longer what this asserts. ``projects_of`` reads ``TaskProject``, so this
    now only pins that ``_task_over`` wrote a declaration covering both
    projects -- not that the resolution declines to filter ``Inactive``, which
    it no longer walks at all. The behaviour named above moved to the
    backfill's SQL, which is where it is guarded now. Kept rather than deleted
    because the assertion is still true and still worth holding: a soft-deleted
    image must not cost its task a declared project.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)

    project_b = make_project(session, "B")
    patient_b = make_patient(session, project_b, "pat-B")
    study_b = make_study(session, patient_b, date(2024, 1, 1))
    series_b = make_series(session, study_b)
    image_b = make_image(session, series_b, device, backend, "img-b", inactive=True)

    task, _ = _task_over(session, [image_a, image_b])
    session.commit()
    assert projects_of(session, Task, task.TaskID) == {
        project_a.ProjectID,
        project_b.ProjectID,
    }


def test_a_task_that_declares_nothing_touches_no_projects(session):
    """The empty declaration -- the shape ``require`` fails closed on.

    ``projects_of`` reads ``TaskProject``, so what produces the empty set is
    the empty declaration and not the absence of images: ``_task_over``
    declares one project per distinct image project, and an empty ``images``
    list declares none.
    """
    task, _ = _task_over(session, [])
    session.commit()
    assert projects_of(session, Task, task.TaskID) == set()


def test_a_form_annotation_resolves_through_its_patient(session):
    """Patient.ProjectID is the sole project authority for a form annotation."""
    from eyened_orm import FormSchema
    from eyened_orm.form_annotation import EntityType

    project = make_project(session, "A")
    patient = make_patient(session, project, "pat-A")
    # A second project + patient, so a resolver returning every project in the
    # database fails here rather than passing by accident.
    make_patient(session, make_project(session, "B"), "pat-B")
    creator = make_creator(session, "alice")
    schema = FormSchema(SchemaName="s", Schema={}, EntityType=EntityType.ImageInstance)
    session.add(schema)
    session.flush()
    annotation = FormAnnotation(
        FormSchemaID=schema.FormSchemaID,
        PatientID=patient.PatientID,
        CreatorID=creator.CreatorID,
    )
    session.add(annotation)
    session.commit()
    assert projects_of(session, FormAnnotation, annotation.FormAnnotationID) == {
        project.ProjectID
    }


@pytest.fixture()
def one_row_each_in_two_projects(session):
    """One ``Study``, ``Series`` and ``ModelSegmentation`` in A, and one in B.

    Seeded A first, so in every one of those tables the *lowest* primary key
    belongs to A. That ordering is the point: it is what lets the B half of the
    round trip below tell "the project of the row you asked about" apart from
    "the project of some arbitrary row of that type".
    """
    from eyened_orm.segmentation import DataRepresentation, Datatype, SegmentationModel

    backend = make_storage_backend(session)
    device = make_device(session, "d")
    # No factory exists for ModelSegmentation: ModelID is NOT NULL and
    # SegmentationModel is a joined-table subclass of Model whose ModelName and
    # Version are NOT NULL too.
    model = SegmentationModel(ModelName="m", Version="1")
    session.add(model)
    session.flush()

    seeded: dict[str, dict] = {}
    for name in ("A", "B"):
        project = make_project(session, name)
        patient = make_patient(session, project, f"pat-{name}")
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        image = make_image(session, series, device, backend, f"img-{name}")
        segmentation = ModelSegmentation(
            ModelID=model.ModelID,
            ImageInstanceID=image.ImageInstanceID,
            DataType=Datatype.R8UI,
            DataRepresentation=DataRepresentation.Binary,
            Depth=1,
            Height=4,
            Width=4,
        )
        session.add(segmentation)
        session.flush()
        seeded[name] = {
            "project": project.ProjectID,
            Study: study.StudyID,
            Series: series.SeriesID,
            ModelSegmentation: segmentation.ModelSegmentationID,
        }
    session.commit()
    return seeded


@pytest.mark.parametrize(
    "entity",
    [Study, Series, ModelSegmentation],
    ids=lambda entity: entity.__name__,
)
def test_a_write_resolver_answers_for_the_row_it_was_asked_about(
    session, one_row_each_in_two_projects, entity
):
    """Both halves, per entity: A resolves to A *and* B resolves to B.

    ``projects_of`` is the write side of the route -- its answer is the set
    ``AccessScope.require`` is judged against at ``study_service`` and
    ``segmentation_service``, so a resolver naming the wrong-but-plausible
    project fails open: the actor is checked against a project they may well
    hold. The read side is thoroughly covered and this side was not, which is
    the asymmetry this test exists to close.

    One project would prove nothing: a resolver ignoring its argument
    altogether still returns the only project there is. Two rows, asserted in
    *both* directions, is the smallest fixture that separates three different
    resolvers from three different wrong answers -- every project in the
    database, some other row's project, and an arbitrary first row's project.
    """
    seeded = one_row_each_in_two_projects
    for name in ("A", "B"):
        row_id = seeded[name][entity]
        assert projects_of(session, entity, row_id) == {seeded[name]["project"]}, (
            f"{entity.__name__} {row_id} should resolve to project {name} alone"
        )


def test_the_batch_image_gate_follows_the_route_declaration(monkeypatch):
    """Fork ``ImageInstance``'s route in the map; ``image_project_pairs`` moves.

    The batch gate is the one selectable that could plausibly be hand-written
    -- it is the only one taking a list and returning pairs, so it does not fit
    ``_project_ids_from`` -- and it was, once. A hand-written
    ``select(ImageInstance.ImageInstanceID, ImageInstance.ProjectID)`` emits
    byte-identical SQL to the derived form on the map as declared, since
    ``_hops_to_column(ImageInstance)`` returns no hops and exactly that column.
    Moving the route is the only thing that separates them, so this test moves
    it.

    Why that drift matters rather than merely offending the module docstring:
    these pairs feed ``AccessScope.require`` in the import-enqueue gate, and a
    gate reading a stale route can *widen*. Should the shared route ever leave
    the denormalized copy -- the one change a reader of this module would
    expect, the copy existing precisely because it might be found unreliable --
    every read filter follows it and a hand-written gate does not. An image
    whose stale ``ProjectID`` names a project the caller holds would be
    enqueued while ``apply_scope`` hid it from the same caller's reads.

    What the suite has otherwise, and why neither sees this: the AST guard in
    ``server/tests/test_import_enqueue_gate.py`` reads the *repository*, so it
    pins which helper is called and never what the helper is built from; and
    ``test_project_ids_for_images_agrees_with_the_shared_resolver`` is
    behavioural but blind here, because the composite foreign keys hold
    ``Series.ProjectID`` equal to ``ImageInstance.ProjectID`` on every row that
    can exist, so a forked route still returns the same answer. Measured
    against the hand-written body this replaced: it is the only test in the
    suite that fails, out of 934.
    """
    ids = [11, 22]
    before = str(image_project_pairs(ids).compile(dialect=sqlite.dialect()))
    # Anti-vacuity for the three assertions at the end: on the map as declared
    # the route ends on the image's own row, so neither string they look for is
    # present yet and the fork is the only thing that can introduce them.
    assert '"ImageInstance"."ProjectID"' in before, before
    assert '"Series"' not in before, before

    monkeypatch.setattr(
        scoping,
        "_OWN_PROJECT_COLUMN",
        {
            entity: column
            for entity, column in scoping._OWN_PROJECT_COLUMN.items()
            if entity is not ImageInstance
        },
    )
    monkeypatch.setattr(
        scoping,
        "_ONE_HOP_TO",
        {
            **scoping._ONE_HOP_TO,
            ImageInstance: (Series, lambda: ImageInstance.SeriesID == Series.SeriesID),
        },
    )

    after = str(image_project_pairs(ids).compile(dialect=sqlite.dialect()))
    assert 'JOIN "Series"' in after, after
    assert '"Series"."ProjectID"' in after, after
    assert '"ImageInstance"."ProjectID"' not in after, after


# --- the correlated EXISTS predicate that apply_scope emits ------------------
#
# The hazard these guard is auto-correlation emptying the subquery's FROM,
# which the shape of the subquery does not change. The set-valued case belongs
# here too, ``_set_valued_predicate`` reading ``TaskProject``: a one-table FROM
# is exactly the shape auto-correlation can empty.


def _grader_scope(*project_ids: int) -> AccessScope:
    return AccessScope(
        actor_id=7,
        username="alice",
        is_admin=False,
        roles={p: ProjectRole.grader for p in project_ids},
    )


@pytest.mark.parametrize(
    "entity", sorted(SET_VALUED_ENTITIES, key=lambda e: e.__name__),
    ids=lambda e: e.__name__,
)
def test_the_task_predicate_compiles_inside_a_query_that_joins_taskproject(entity):
    """``_set_valued_predicate``'s ``.correlate(entity)`` is what makes this legal.

    Since the predicate reads the declaration, the subquery's *entire* FROM is
    ``TaskProject`` -- one table, which is exactly what auto-correlation can
    empty. An enclosing query that joins ``TaskProject`` itself therefore
    raises ``InvalidRequestError: ... returned no FROM clauses due to
    auto-correlation`` the moment the call is dropped, on both branches.

    Without this test, deleting ``.correlate(entity)`` leaves the whole suite
    green, because no read in the codebase reaches this shape:
    ``declared_projects`` and ``projects_for_tasks`` do select FROM
    ``TaskProject`` in their outer query, but reach the predicate through a
    subquery whose own FROM is ``Task``, and auto-correlation does not cross
    that level -- compiling ``projects_for_tasks`` with the correlation removed
    still succeeds. So the shape is built here rather than borrowed from a
    caller: the claim is about the predicate, and has to be checkable without
    waiting for a caller to grow into it.

    Compiling is the assertion; two string checks stop a predicate that
    degenerated into something trivially compilable from passing. **Each has to
    be read off a different query.** ``FROM "TaskProject"`` belongs on the
    joined query, where auto-correlation is the thing that would remove it. The
    correlation does not: the join written here emits
    ``"TaskProject"."TaskID" = "<entity>"."TaskID"`` itself, so asserting that
    string against this SQL holds whatever the predicate does -- which is what
    the first version of this test asserted, and both degenerations named just
    below passed it. Compiled without the join, the equality can only have come from
    the predicate, so it discriminates: dropping the correlating ``WHERE``
    (keyed on nothing) removes it, and keying ``TaskProject`` on itself
    replaces it. Both verified failing, for both entities.

    Both checks also fire if the predicate stops reading ``TaskProject`` at
    all -- measured, not intended, and not this test's job: the behavioural
    coverage for that mechanism lives in
    ``server/tests/test_task_containment_routes.py``.
    """
    joined = (
        select(entity)
        .join(TaskProject, TaskProject.TaskID == entity.TaskID)
        .where(scope_criteria(entity, _grader_scope(1)))
    )
    # The subquery kept a FROM of its own, under an enclosing query holding the
    # one table it has.
    assert 'FROM "TaskProject"' in str(joined.compile(dialect=sqlite.dialect()))

    # ...and it is keyed on the outer entity's row -- not on itself, and not on
    # nothing. Read off a query that joins nothing, because there the only
    # thing that can emit this equality is the predicate.
    alone = select(entity).where(scope_criteria(entity, _grader_scope(1)))
    assert f'"TaskProject"."TaskID" = "{entity.__tablename__}"."TaskID"' in str(
        alone.compile(dialect=sqlite.dialect())
    )


@pytest.mark.parametrize(
    "entity", sorted(SINGLE_PROJECT_ENTITIES, key=lambda e: e.__name__),
    ids=lambda e: e.__name__,
)
def test_apply_scope_compiles_inside_a_query_that_holds_every_route_table(entity):
    """Every entry must survive an enclosing query that already holds its FROM.

    SQLAlchemy *auto*-correlation strips from a subquery's FROM every table the
    enclosing query already has. An entry whose FROM is then empty raises
    ``InvalidRequestError: ... returned no FROM clauses due to
    auto-correlation``, and the search layer builds exactly such a shape
    (``join_from(Study, Patient, ...)``), so the read path would 500.

    Four of the eleven cases are now immune for free: the
    ``_OWN_PROJECT_COLUMN`` entities -- Patient, Study, Series, ImageInstance
    -- emit a bare ``ProjectID IN (...)`` with no subquery at all, so
    auto-correlation has nothing to strip.

    The seven one-hop entries are the exposure, and it is *sharp*: five
    (Segmentation, ModelSegmentation, FormAnnotation, StudyTagLink,
    ImageInstanceTagLink) select FROM a bare table, which is exactly what
    auto-correlation matches by identity. ``.correlate(entity)`` is the only
    thing holding them up.

    So the enclosing query is derived from ``_ONE_HOP_TO`` rather than
    hardcoding Patient: it holds every table some entry hops to -- Patient
    among them today, and kept explicitly so the shape survives a map that
    stops hopping there -- which is what it takes for one shape to reach all
    five. Hardcoding Patient reached only FormAnnotation; the other four select
    FROM ImageInstance or Study, which that query never held. **Five is the
    ceiling**, not a gap: SegmentationTagLink and FormAnnotationTagLink select
    FROM a multi-table ``Join`` object, which auto-correlation cannot match
    against an enclosing table by identity, so those two are *structurally
    immune*. Dropping ``.correlate(entity)`` fails exactly the five and leaves
    those two green; do not read that as something left to cover.

    The assertion is read off the WHERE clause rather than the whole statement,
    because ``"ProjectID" in sql`` is already true of
    ``select(Patient|Study|Series|ImageInstance)`` with no predicate at all --
    the column is in the SELECT list, so for those four an ``apply_scope`` that
    returned the statement untouched would pass. The unscoped compile is the
    control: the enclosing query contributes no WHERE of its own, so a WHERE
    mentioning ProjectID can only have come from the predicate.

    Parametrized over the registry so a future entity is covered without anyone
    remembering to add a case.
    """
    reached = sorted(
        ({parent for parent, _ in _ONE_HOP_TO.values()} | {Patient}) - {entity},
        key=lambda e: e.__name__,
    )
    stmt = select(entity).select_from(entity, *reached)
    unscoped = str(stmt.compile(dialect=sqlite.dialect()))
    assert "WHERE " not in unscoped, unscoped
    # Anti-vacuity for the derivation itself: with ``reached`` empty every
    # assertion below still passes -- even with ``.correlate(entity)`` dropped
    # -- so the test could silently fall from catching five exposures to none.
    #
    # Matched against the FROM clause, and quoted: a bare ``ImageInstance in
    # unscoped`` is satisfied by ``"Segmentation"."ImageInstanceID"`` in the
    # SELECT list, so it holds under an empty ``reached`` for all seven.
    if entity in _ONE_HOP_TO:
        from_clause = unscoped.rpartition("FROM ")[2]
        assert f'"{_ONE_HOP_TO[entity][0].__tablename__}"' in from_clause, unscoped

    scoped = apply_scope(stmt, entity, _grader_scope(1))
    sql = str(scoped.compile(dialect=sqlite.dialect()))
    _, keyword, where = sql.partition("WHERE ")
    assert keyword, sql
    assert "ProjectID" in where, sql


def test_apply_scope_filters_a_study_to_one_project(session):
    """Compiling is not filtering: prove the correlation binds to the outer row.

    Without this a degenerate predicate -- correlated against the wrong table,
    or not correlated at all -- would still compile and still pass the test
    above while returning every study or none.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)
    _image_in(session, "B", "img-b", backend, device)
    session.commit()
    project_a_id = project_a.ProjectID
    study_a_id = session.scalars(
        select(Series.StudyID).where(Series.SeriesID == image_a.SeriesID)
    ).one()

    found = session.scalars(
        apply_scope(
            select(Study.StudyID).join(Patient, Patient.PatientID == Study.PatientID),
            Study,
            _grader_scope(project_a_id),
        )
    ).all()
    assert set(found) == {study_a_id}


def test_apply_scope_filters_an_image_to_one_project(session):
    """The same proof one level deeper, through Series and Study.

    Without this, an image-level predicate that resolved to the wrong join
    chain would be caught only in the API.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a, image_a = _image_in(session, "A", "img-a", backend, device)
    _image_in(session, "B", "img-b", backend, device)
    session.commit()
    project_a_id = project_a.ProjectID
    image_a_id = image_a.ImageInstanceID

    found = session.scalars(
        apply_scope(
            select(ImageInstance.ImageInstanceID)
            .join(Series, Series.SeriesID == ImageInstance.SeriesID)
            .join(Study, Study.StudyID == Series.StudyID)
            .join(Patient, Patient.PatientID == Study.PatientID),
            ImageInstance,
            _grader_scope(project_a_id),
        )
    ).all()
    assert set(found) == {image_a_id}
