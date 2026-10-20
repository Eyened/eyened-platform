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


# PascalCase. Comment this block and uncomment the lowercase block below.
SubTask = "SubTask"
SubTaskImageLink = "SubTaskImageLink"
ImageInstance = "ImageInstance"
TaskProject = "TaskProject"
SubTaskID = "SubTaskID"
TaskID = "TaskID"
ProjectID = "ProjectID"
ImageInstanceID = "ImageInstanceID"
FK_LINK_IMAGE = "SubTaskImageLink_ibfk_1"
FK_LINK_SUBTASK = "SubTaskImageLink_ibfk_2"

# SubTask = "subtask"
# SubTaskImageLink = "subtaskimagelink"
# ImageInstance = "imageinstance"
# TaskProject = "taskproject"
# SubTaskID = "subtaskid"
# TaskID = "taskid"
# ProjectID = "projectid"
# ImageInstanceID = "imageinstanceid"
# FK_LINK_IMAGE = "subtaskimagelink_ibfk_1"
# FK_LINK_SUBTASK = "subtaskimagelink_ibfk_2"


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE {SubTaskImageLink}
            ADD COLUMN {TaskID} INT NULL,
            ADD COLUMN {ProjectID} INT NULL
    """)
    op.execute(f"""
        UPDATE {SubTaskImageLink} l
        JOIN {SubTask} st ON st.{SubTaskID} = l.{SubTaskID}
        JOIN {ImageInstance} ii ON ii.{ImageInstanceID} = l.{ImageInstanceID}
        SET l.{TaskID} = st.{TaskID}, l.{ProjectID} = ii.{ProjectID}
    """)
    op.execute(f"""
        ALTER TABLE {SubTask}
        ADD UNIQUE INDEX uq_SubTask_SubTask_Task ({SubTaskID}, {TaskID})
    """)
    # fk_SubTaskImageLink_TaskProject rejects any link whose task has not
    # declared that project. MODIFY fails, or writes 0, if the UPDATE missed a row.
    op.execute(f"""
        ALTER TABLE {SubTaskImageLink}
            MODIFY {TaskID} INT NOT NULL,
            MODIFY {ProjectID} INT NOT NULL,
            ADD INDEX ix_SubTaskImageLink_Image_Project ({ImageInstanceID}, {ProjectID}, {SubTaskID}),
            ADD INDEX ix_SubTaskImageLink_SubTask_Task ({SubTaskID}, {TaskID}),
            ADD INDEX ix_SubTaskImageLink_Task_Project ({TaskID}, {ProjectID}),
            ADD CONSTRAINT fk_SubTaskImageLink_SubTask_Task
                FOREIGN KEY ({SubTaskID}, {TaskID})
                REFERENCES {SubTask} ({SubTaskID}, {TaskID})
                ON UPDATE CASCADE ON DELETE CASCADE,
            ADD CONSTRAINT fk_SubTaskImageLink_Image_Project
                FOREIGN KEY ({ImageInstanceID}, {ProjectID})
                REFERENCES {ImageInstance} ({ImageInstanceID}, {ProjectID})
                ON UPDATE CASCADE ON DELETE CASCADE,
            ADD CONSTRAINT fk_SubTaskImageLink_TaskProject
                FOREIGN KEY ({TaskID}, {ProjectID})
                REFERENCES {TaskProject} ({TaskID}, {ProjectID}),
            DROP FOREIGN KEY `{FK_LINK_SUBTASK}`,
            DROP FOREIGN KEY `{FK_LINK_IMAGE}`,
            DROP INDEX ix_SubTaskImageLink_Image_SubTask,
            DROP INDEX fk_SubTaskImageLink_SubTask1_idx,
            DROP INDEX fk_SubTaskImageLink_ImageInstance1_idx
    """)


def downgrade() -> None:
    op.execute(f"""
        ALTER TABLE {SubTaskImageLink}
            DROP FOREIGN KEY fk_SubTaskImageLink_SubTask_Task,
            DROP FOREIGN KEY fk_SubTaskImageLink_Image_Project,
            DROP FOREIGN KEY fk_SubTaskImageLink_TaskProject,
            DROP INDEX ix_SubTaskImageLink_Image_Project,
            DROP INDEX ix_SubTaskImageLink_SubTask_Task,
            DROP INDEX ix_SubTaskImageLink_Task_Project,
            DROP COLUMN {TaskID},
            DROP COLUMN {ProjectID}
    """)
    op.execute(f"ALTER TABLE {SubTask} DROP INDEX uq_SubTask_SubTask_Task")
    op.execute(f"""
        ALTER TABLE {SubTaskImageLink}
            ADD CONSTRAINT fk_SubTaskImageLink_SubTask_single
                FOREIGN KEY ({SubTaskID}) REFERENCES {SubTask} ({SubTaskID}) ON DELETE CASCADE,
            ADD CONSTRAINT fk_SubTaskImageLink_Image_single
                FOREIGN KEY ({ImageInstanceID}) REFERENCES {ImageInstance} ({ImageInstanceID})
                ON DELETE CASCADE
    """)
