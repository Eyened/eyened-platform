"""Task import: expand grouped (subtask, images) → flat rows; integration with images."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from eyened_orm import ImageInstance, SubTask, SubTaskImageLink, Task
from eyened_orm.importer.importer import plan_image_import, plan_import
from eyened_orm.importer.importer_dtos import ImportRow, ImportTaskRow, expand_task_import_rows
from eyened_orm.importer.importer_mappings_tasks import TASK_ENTITY_SPECS
from eyened_orm.task import TaskState


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_expand_task_import_rows_doc_example():
    """Two groups ``[a,b,c]`` and ``[a,d,e]`` → six flat rows; anon 1 then 2; indices per group."""
    shared = ImportTaskRow(
        task_definition_name="td",
        task_name="t1",
        creator_name="c",
        contact_email="x@y.z",
        task_state=TaskState.Busy,
    )
    a, b, c, d, e = 101, 102, 103, 104, 105
    rows = expand_task_import_rows(
        shared,
        [[a, b, c], [a, d, e]],
    )
    assert len(rows) == 6
    assert [r.image_instance_id for r in rows] == [a, b, c, a, d, e]
    assert [r.subtask_anonymous_identity for r in rows] == [1, 1, 1, 2, 2, 2]
    assert [r.subtask_image_index for r in rows] == [0, 1, 2, 0, 1, 2]
    assert all(
        r.task_definition_name == "td"
        and r.contact_email == "x@y.z"
        and r.task_state == TaskState.Busy
        for r in rows
    )


def test_expand_empty_or_skipped_image_lists():
    assert expand_task_import_rows(ImportTaskRow(creator_name="c"), []) == []
    assert expand_task_import_rows(ImportTaskRow(creator_name="c"), [[]]) == []


def test_plan_import_grouped_subtasks_and_images(session):
    """Five images; two anonymous subtasks with overlapping image ids → flat expand → DB."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "tm",
        "manufacturer_model_name": "tmm",
        "device_description": "td",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    d = date(2026, 4, 1)
    img_rows = [
        ImportRow(
            project_name="ex-proj",
            patient_identifier="ex-pat",
            study_date=d,
            series_instance_uid="ex-ser",
            storage_backend_key="ex-sb",
            object_key=f"ex-{i}.png",
            modality="ColorFundus",
            laterality="R",
        )
        for i in range(5)
    ]
    plan_image_import(session, img_rows, defaults=defaults).apply()
    session.commit()

    ids = list(
        session.scalars(
            select(ImageInstance.ImageInstanceID).order_by(ImageInstance.ImageInstanceID)
        ).all()
    )
    assert len(ids) >= 5
    i0, i1, i2, i3, i4 = ids[0], ids[1], ids[2], ids[3], ids[4]

    task_rows = expand_task_import_rows(
        ImportTaskRow(
            task_definition_name="td-ex",
            task_name="t-ex",
            creator_name="creator-ex",
        ),
        [[i0, i1, i2], [i0, i3, i4]],
    )
    plan_import(
        session,
        task_rows,
        entity_specs=TASK_ENTITY_SPECS,
    ).apply()
    session.commit()

    assert _count(session, Task) == 1
    assert _count(session, SubTask) == 2
    assert _count(session, SubTaskImageLink) == 6

    sets = []
    for link in session.scalars(select(SubTaskImageLink)).all():
        sets.append(link.ImageInstanceID)
    assert set(sets) == {i0, i1, i2, i3, i4}
    # i0 appears on both subtasks → six links, five distinct images
    assert sets.count(i0) == 2
