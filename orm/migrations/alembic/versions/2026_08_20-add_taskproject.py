"""Create TaskProject and fill it from the image links.

Revision ID: 99724789b34d
Revises: 4eae42457fa2
"""
from typing import Sequence, Union

from alembic import op


revision: str = "99724789b34d"
down_revision: Union[str, None] = "4eae42457fa2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PascalCase. Comment this block and uncomment the lowercase block below.
TaskProject = "TaskProject"
Task = "Task"
Project = "Project"
SubTask = "SubTask"
SubTaskImageLink = "SubTaskImageLink"
ImageInstance = "ImageInstance"
Series = "Series"
Study = "Study"
Patient = "Patient"
TaskID = "TaskID"
ProjectID = "ProjectID"
SubTaskID = "SubTaskID"
ImageInstanceID = "ImageInstanceID"
SeriesID = "SeriesID"
StudyID = "StudyID"
PatientID = "PatientID"
DateInserted = "DateInserted"

# TaskProject = "taskproject"
# Task = "task"
# Project = "project"
# SubTask = "subtask"
# SubTaskImageLink = "subtaskimagelink"
# ImageInstance = "imageinstance"
# Series = "series"
# Study = "study"
# Patient = "patient"
# TaskID = "taskid"
# ProjectID = "projectid"
# SubTaskID = "subtaskid"
# ImageInstanceID = "imageinstanceid"
# SeriesID = "seriesid"
# StudyID = "studyid"
# PatientID = "patientid"
# DateInserted = "dateinserted"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {TaskProject} (
            {TaskID} INT NOT NULL,
            {ProjectID} INT NOT NULL,
            {DateInserted} DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY ({TaskID}, {ProjectID}),
            CONSTRAINT fk_TaskProject_Task FOREIGN KEY ({TaskID})
                REFERENCES {Task} ({TaskID}) ON DELETE CASCADE,
            CONSTRAINT fk_TaskProject_Project FOREIGN KEY ({ProjectID})
                REFERENCES {Project} ({ProjectID}) ON DELETE RESTRICT
        )
    """)
    op.execute(f"CREATE INDEX ix_TaskProject_Project ON {TaskProject} ({ProjectID})")
    # Later, fk_SubTaskImageLink_TaskProject refuses a link with no matching row here.
    op.execute(f"""
        INSERT INTO {TaskProject} ({TaskID}, {ProjectID})
        SELECT DISTINCT st.{TaskID}, p.{ProjectID}
        FROM {SubTask} st
        JOIN {SubTaskImageLink} sil ON sil.{SubTaskID} = st.{SubTaskID}
        JOIN {ImageInstance} ii ON ii.{ImageInstanceID} = sil.{ImageInstanceID}
        JOIN {Series} se ON se.{SeriesID} = ii.{SeriesID}
        JOIN {Study} sy ON sy.{StudyID} = se.{StudyID}
        JOIN {Patient} p ON p.{PatientID} = sy.{PatientID}
    """)


def downgrade() -> None:
    op.execute(f"DROP TABLE {TaskProject}")
