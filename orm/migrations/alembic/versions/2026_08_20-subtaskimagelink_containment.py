"""Copy TaskID and ProjectID onto SubTaskImageLink and point them at TaskProject.

Revision ID: 2db0e63195db
Revises: b45090e1544e
"""
from typing import Sequence, Union

from alembic import op


revision: str = "2db0e63195db"
down_revision: Union[str, None] = "b45090e1544e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PascalCase. For a lowercase database, comment these and uncomment the next line.
SubTask = "SubTask"
# SubTask = "subtask"
Task = "Task"
# Task = "task"
SubTaskImageLink = "SubTaskImageLink"
# SubTaskImageLink = "subtaskimagelink"
ImageInstance = "ImageInstance"
# ImageInstance = "imageinstance"
TaskProject = "TaskProject"
# TaskProject = "taskproject"
SubTaskID = "SubTaskID"
# SubTaskID = "subtaskid"
TaskID = "TaskID"
# TaskID = "taskid"
ProjectID = "ProjectID"
# ProjectID = "projectid"
ImageInstanceID = "ImageInstanceID"
# ImageInstanceID = "imageinstanceid"
FK_SUBTASK_TASK = "SubTask_ibfk_1"
# FK_SUBTASK_TASK = "subtask_ibfk_1"
# A database built from orm_baseline stored this as SubTask_ibfk_2.
FK_LINK_IMAGE = "SubTaskImageLink_ibfk_1"
# FK_LINK_IMAGE = "subtaskimagelink_ibfk_1"
FK_LINK_SUBTASK = "SubTaskImageLink_ibfk_2"
# FK_LINK_SUBTASK = "subtaskimagelink_ibfk_2"


def upgrade() -> None:
    # subtask_ibfk_1 sorts after fk_TaskProject_Task, and DELETE FROM Task then
    # fails with error 1451. SubTask_ibfk_1 already sorts first; this rename is
    # still run so both databases end on the same name. Error 1091: wrong constant.
    op.execute(
        f"ALTER TABLE {SubTask} "
        f"DROP FOREIGN KEY `{FK_SUBTASK_TASK}`, "
        f"ADD CONSTRAINT fk_SubTask_Task "
        f"FOREIGN KEY ({TaskID}) REFERENCES {Task} ({TaskID}) ON DELETE CASCADE"
    )
    op.execute(
        f"ALTER TABLE {SubTaskImageLink} "
        f"ADD COLUMN {TaskID} INT NULL, "
        f"ADD COLUMN {ProjectID} INT NULL"
    )
    op.execute(
        f"UPDATE {SubTaskImageLink} l "
        f"JOIN {SubTask} st ON st.{SubTaskID} = l.{SubTaskID} "
        f"JOIN {ImageInstance} ii ON ii.{ImageInstanceID} = l.{ImageInstanceID} "
        f"SET l.{TaskID} = st.{TaskID}, l.{ProjectID} = ii.{ProjectID}"
    )
    op.execute(
        f"ALTER TABLE {SubTask} ADD UNIQUE INDEX uq_SubTask_SubTask_Task "
        f"({SubTaskID}, {TaskID})"
    )
    # fk_SubTaskImageLink_TaskProject rejects any link whose task has not
    # declared that project. MODIFY fails, or writes 0, if the UPDATE missed a row.
    op.execute(
        f"ALTER TABLE {SubTaskImageLink} "
        f"MODIFY {TaskID} INT NOT NULL, "
        f"MODIFY {ProjectID} INT NOT NULL, "
        f"ADD INDEX ix_SubTaskImageLink_Image_Project "
        f"({ImageInstanceID}, {ProjectID}, {SubTaskID}), "
        f"ADD INDEX ix_SubTaskImageLink_SubTask_Task ({SubTaskID}, {TaskID}), "
        f"ADD INDEX ix_SubTaskImageLink_Task_Project ({TaskID}, {ProjectID}), "
        f"ADD CONSTRAINT fk_SubTaskImageLink_SubTask_Task "
        f"FOREIGN KEY ({SubTaskID}, {TaskID}) "
        f"REFERENCES {SubTask} ({SubTaskID}, {TaskID}) "
        f"ON UPDATE CASCADE ON DELETE CASCADE, "
        f"ADD CONSTRAINT fk_SubTaskImageLink_Image_Project "
        f"FOREIGN KEY ({ImageInstanceID}, {ProjectID}) "
        f"REFERENCES {ImageInstance} ({ImageInstanceID}, {ProjectID}) "
        f"ON UPDATE CASCADE ON DELETE CASCADE, "
        f"ADD CONSTRAINT fk_SubTaskImageLink_TaskProject "
        f"FOREIGN KEY ({TaskID}, {ProjectID}) "
        f"REFERENCES {TaskProject} ({TaskID}, {ProjectID}), "
        f"DROP FOREIGN KEY `{FK_LINK_SUBTASK}`, "
        f"DROP FOREIGN KEY `{FK_LINK_IMAGE}`, "
        f"DROP INDEX ix_SubTaskImageLink_Image_SubTask, "
        f"DROP INDEX fk_SubTaskImageLink_SubTask1_idx, "
        f"DROP INDEX fk_SubTaskImageLink_ImageInstance1_idx"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {SubTaskImageLink} "
        f"DROP FOREIGN KEY fk_SubTaskImageLink_SubTask_Task, "
        f"DROP FOREIGN KEY fk_SubTaskImageLink_Image_Project, "
        f"DROP FOREIGN KEY fk_SubTaskImageLink_TaskProject, "
        f"DROP INDEX ix_SubTaskImageLink_Image_Project, "
        f"DROP INDEX ix_SubTaskImageLink_SubTask_Task, "
        f"DROP INDEX ix_SubTaskImageLink_Task_Project, "
        f"DROP COLUMN {TaskID}, "
        f"DROP COLUMN {ProjectID}"
    )
    op.execute(f"ALTER TABLE {SubTask} DROP INDEX uq_SubTask_SubTask_Task")
    op.execute(
        f"ALTER TABLE {SubTaskImageLink} "
        f"ADD CONSTRAINT fk_SubTaskImageLink_SubTask_single "
        f"FOREIGN KEY ({SubTaskID}) REFERENCES {SubTask} ({SubTaskID}) ON DELETE CASCADE, "
        f"ADD CONSTRAINT fk_SubTaskImageLink_Image_single "
        f"FOREIGN KEY ({ImageInstanceID}) REFERENCES {ImageInstance} ({ImageInstanceID}) "
        f"ON DELETE CASCADE"
    )
