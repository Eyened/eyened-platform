from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from eyened_orm import ImageInstance, SubTask, SubTaskImageLink, Task
from eyened_orm.importer.importer import plan_image_import, plan_import
from eyened_orm.importer.importer_dtos import ImportRow, ImportTaskRow, expand_task_import_rows
from eyened_orm.importer.importer_mappings_tasks import TASK_ENTITY_SPECS


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_image_then_task_import_creates_tasks_subtasks_and_links(session):
    """Image import materializes instances; task import links them via ``ImageInstanceID`` only."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "tm",
        "manufacturer_model_name": "tmm",
        "device_description": "td",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    d = date(2026, 3, 1)

    img_rows = [
        ImportRow(
            project_name="ti-proj",
            patient_identifier="ti-pat",
            study_date=d,
            series_instance_uid="ti-ser",
            storage_backend_key="ti-sb",
            object_key=f"ti-{i}.png",
            modality="ColorFundus",
            laterality="L",
        )
        for i in range(3)
    ]
    r_img = plan_image_import(session, img_rows, defaults=defaults)
    r_img.apply()
    session.commit()

    ids = list(
        session.scalars(
            select(ImageInstance.ImageInstanceID).order_by(ImageInstance.ImageInstanceID)
        ).all()
    )
    assert len(ids) >= 3
    i0, i1, i2 = ids[0], ids[1], ids[2]

    task_rows = expand_task_import_rows(
        ImportTaskRow(
            task_definition_name="td-mini",
            task_name="t-mini",
            creator_name="creator-mini",
        ),
        [[i0, i1], [i2]],
    )

    r_task = plan_import(
        session,
        task_rows,
        entity_specs=TASK_ENTITY_SPECS,
    )
    r_task.apply()
    session.commit()

    assert _count(session, Task) == 1
    assert _count(session, SubTask) == 2
    assert _count(session, SubTaskImageLink) == 3

    links = session.scalars(select(SubTaskImageLink)).all()
    image_ids = {link.ImageInstanceID for link in links}
    assert image_ids == {i0, i1, i2}


def test_subtask_image_link_rejects_unknown_image_instance_id(session):
    """Applying a task row whose ``image_instance_id`` does not exist violates the link FK."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "tm",
        "manufacturer_model_name": "tmm",
        "device_description": "td",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    d = date(2026, 7, 1)
    plan_image_import(
        session,
        [
            ImportRow(
                project_name="ti-fk-proj",
                patient_identifier="ti-fk-pat",
                study_date=d,
                series_instance_uid="ti-fk-ser",
                storage_backend_key="ti-fk-sb",
                object_key="ti-fk-0.png",
                modality="ColorFundus",
                laterality="L",
            )
        ],
        defaults=defaults,
    ).apply()
    session.commit()

    bad_id = 9_999_999
    assert session.get(ImageInstance, bad_id) is None

    row = ImportTaskRow(
        task_definition_name="td-fk",
        task_name="t-fk",
        creator_name="c-fk",
        subtask_anonymous_identity=1,
        image_instance_id=bad_id,
        subtask_image_index=0,
    )
    run = plan_import(session, [row], entity_specs=TASK_ENTITY_SPECS)
    with pytest.raises(IntegrityError):
        run.apply()


def test_append_subtask_image_link_with_existing_task_and_subtask_ids(session):
    """After an anonymous subtask import, a follow-up row can add a link using ``task_id`` and ``subtask_id``."""
    defaults = {
        "project_external": "Y",
        "manufacturer": "tm",
        "manufacturer_model_name": "tmm",
        "device_description": "td",
        "dataset_identifier": "",
        "storage_backend_kind": "local",
    }
    d = date(2026, 7, 2)
    plan_image_import(
        session,
        [
            ImportRow(
                project_name="ti-st-proj",
                patient_identifier="ti-st-pat",
                study_date=d,
                series_instance_uid="ti-st-ser",
                storage_backend_key="ti-st-sb",
                object_key=f"ti-st-{i}.png",
                modality="ColorFundus",
                laterality="L",
            )
            for i in range(2)
        ],
        defaults=defaults,
    ).apply()
    session.commit()

    ids = list(
        session.scalars(
            select(ImageInstance.ImageInstanceID).order_by(ImageInstance.ImageInstanceID)
        ).all()
    )
    i0, i1 = ids[0], ids[1]

    plan_import(
        session,
        expand_task_import_rows(
            ImportTaskRow(
                task_definition_name="td-st",
                task_name="t-st",
                creator_name="c-st",
            ),
            [[i0]],
        ),
        entity_specs=TASK_ENTITY_SPECS,
    ).apply()
    session.commit()

    st = session.scalar(select(SubTask))
    task = session.scalar(select(Task))
    assert st is not None and task is not None

    plan_import(
        session,
        [
            ImportTaskRow(
                task_definition_name="td-st",
                task_name="t-st",
                creator_name="c-st",
                task_id=task.TaskID,
                subtask_id=st.SubTaskID,
                image_instance_id=i1,
                subtask_image_index=1,
            )
        ],
        entity_specs=TASK_ENTITY_SPECS,
    ).apply()
    session.commit()

    links = session.scalars(select(SubTaskImageLink)).all()
    assert len(links) == 2
    assert {link.ImageInstanceID for link in links} == {i0, i1}
    assert all(link.SubTaskID == st.SubTaskID for link in links)
