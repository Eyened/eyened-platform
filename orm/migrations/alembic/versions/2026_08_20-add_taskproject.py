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


# PascalCase. For a lowercase database, comment these and uncomment the next line.
TaskProject = "TaskProject"
# TaskProject = "taskproject"
Task = "Task"
# Task = "task"
Project = "Project"
# Project = "project"
SubTask = "SubTask"
# SubTask = "subtask"
SubTaskImageLink = "SubTaskImageLink"
# SubTaskImageLink = "subtaskimagelink"
ImageInstance = "ImageInstance"
# ImageInstance = "imageinstance"
Series = "Series"
# Series = "series"
Study = "Study"
# Study = "study"
Patient = "Patient"
# Patient = "patient"
TaskID = "TaskID"
# TaskID = "taskid"
ProjectID = "ProjectID"
# ProjectID = "projectid"
SubTaskID = "SubTaskID"
# SubTaskID = "subtaskid"
ImageInstanceID = "ImageInstanceID"
# ImageInstanceID = "imageinstanceid"
SeriesID = "SeriesID"
# SeriesID = "seriesid"
StudyID = "StudyID"
# StudyID = "studyid"
PatientID = "PatientID"
# PatientID = "patientid"
DateInserted = "DateInserted"
# DateInserted = "dateinserted"


def upgrade() -> None:
    op.execute(
        f"CREATE TABLE {TaskProject} ("
        f"{TaskID} INT NOT NULL, "
        f"{ProjectID} INT NOT NULL, "
        f"{DateInserted} DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        f"PRIMARY KEY ({TaskID}, {ProjectID}), "
        f"CONSTRAINT fk_TaskProject_Task FOREIGN KEY ({TaskID}) "
        f"REFERENCES {Task} ({TaskID}) ON DELETE CASCADE, "
        f"CONSTRAINT fk_TaskProject_Project FOREIGN KEY ({ProjectID}) "
        f"REFERENCES {Project} ({ProjectID}) ON DELETE RESTRICT)"
    )
    op.execute(
        f"CREATE INDEX ix_TaskProject_Project ON {TaskProject} ({ProjectID})"
    )
    # Later, fk_SubTaskImageLink_TaskProject refuses a link with no matching row here.
    op.execute(
        f"INSERT INTO {TaskProject} ({TaskID}, {ProjectID}) "
        f"SELECT DISTINCT st.{TaskID}, p.{ProjectID} "
        f"FROM {SubTask} st "
        f"JOIN {SubTaskImageLink} sil ON sil.{SubTaskID} = st.{SubTaskID} "
        f"JOIN {ImageInstance} ii ON ii.{ImageInstanceID} = sil.{ImageInstanceID} "
        f"JOIN {Series} se ON se.{SeriesID} = ii.{SeriesID} "
        f"JOIN {Study} sy ON sy.{StudyID} = se.{StudyID} "
        f"JOIN {Patient} p ON p.{PatientID} = sy.{PatientID}"
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE {TaskProject}")
