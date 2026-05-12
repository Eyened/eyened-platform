from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from eyened_orm import ImageInstance, SubTask, SubTaskImageLink, Task
from eyened_orm.importer.importer import plan_image_import, plan_import
from eyened_orm.importer.importer_dtos import ImportRow, ImportTaskRow, expand_task_import_rows
from eyened_orm.importer.importer_mappings_tasks import TASK_ENTITY_SPECS


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_plan_import_task_graph_creates_task_subtasks_and_links(session):
    """Image graph creates real rows; task graph references ImageInstanceID only (FK)."""
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
