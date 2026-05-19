"""
Task-side importer entity graph (independent from the image graph).

Hierarchy: ``TaskDefinition`` → ``Task`` (optional ``Contact`` / ``Creator``) →
``SubTask`` → ``SubTaskImageLink`` with ``ImageInstanceID`` taken from the flat row
(FK only — no ``ImageInstance`` :class:`Entity`).

The join table is still an :class:`Entity` so the generic importer can persist it;
lookup is ``(SubTaskID, ImageInstanceID)`` with the image id read from the row.
"""

from __future__ import annotations

from eyened_orm import (
    Creator,
    SubTask,
    SubTaskImageLink,
    Task,
    TaskDefinition,
)

from .importer_mappings_base import CONTACT, Entity, key, lookup, opt, req

CREATOR = Entity(
    model=Creator,
    pk_column="CreatorID",
    pk_row_field="creator_id",
    lookups=(lookup(key("CreatorName")),),
    fields={
        "CreatorName": "creator_name",
        "EmployeeIdentifier": "creator_employee_identifier",
        "IsHuman": "creator_is_human",
        "Description": "creator_description",
    },
)

TASK_DEFINITION = Entity(
    model=TaskDefinition,
    pk_column="TaskDefinitionID",
    pk_row_field="task_definition_id",
    lookups=(lookup(key("TaskDefinitionName")),),
    fields={
        "TaskDefinitionName": "task_definition_name",
        "TaskConfig": "task_definition_config",
    },
)

TASK = Entity(
    model=Task,
    pk_column="TaskID",
    pk_row_field="task_id",
    lookups=(
        lookup(
            key("TaskDefinitionID", TASK_DEFINITION),
            key("TaskName"),
        ),
    ),
    implies=(
        req(TASK_DEFINITION, "TaskDefinition"),
        opt(CONTACT, "Contact"),
        opt(CREATOR, "Creator"),
    ),
    fields={
        "TaskName": "task_name",
        "Description": "task_description",
        "TaskState": "task_state",
    },
)

SUBTASK = Entity(
    model=SubTask,
    pk_column="SubTaskID",
    pk_row_field="subtask_id",
    lookups=(lookup(key("TaskID", TASK), key("SubTaskID")),),
    anonymous_identity="subtask_anonymous_identity",
    implies=(
        req(TASK, "Task"),
        opt(CREATOR, "Creator"),
    ),
    fields={
        "TaskID": "task_id",
        "SubTaskID": "subtask_id",
        "Comments": "subtask_comments",
        "TaskState": "subtask_state",
    },
)

SUBTASK_IMAGE_LINK = Entity(
    model=SubTaskImageLink,
    pk_column=("SubTaskID", "ImageInstanceID"),
    pk_row_field="subtask_image_link_id",
    lookups=(
        lookup(
            key("SubTaskID", SUBTASK),
            key("ImageInstanceID"),
        ),
    ),
    implies=(req(SUBTASK, "SubTask"),),
    fields={
        "ImageInstanceID": "image_instance_id",
        "ImageIndex": "subtask_image_index",
    },
)

TASK_ENTITY_SPECS = (
    CONTACT,
    CREATOR,
    TASK_DEFINITION,
    TASK,
    SUBTASK,
    SUBTASK_IMAGE_LINK,
)
