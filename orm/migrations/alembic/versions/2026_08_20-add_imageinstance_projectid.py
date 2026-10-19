"""Copy Patient.ProjectID onto ImageInstance.

Revision ID: d3ce100ab2b6
Revises: orm_baseline
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d3ce100ab2b6"
down_revision: Union[str, None] = "orm_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PascalCase. For a lowercase database, comment these and uncomment the next line.
ImageInstance = "ImageInstance"
# ImageInstance = "imageinstance"
Series = "Series"
# Series = "series"
Study = "Study"
# Study = "study"
Patient = "Patient"
# Patient = "patient"
ProjectID = "ProjectID"
# ProjectID = "projectid"
ImageInstanceID = "ImageInstanceID"
# ImageInstanceID = "imageinstanceid"
SeriesID = "SeriesID"
# SeriesID = "seriesid"
StudyID = "StudyID"
# StudyID = "studyid"
PatientID = "PatientID"
# PatientID = "patientid"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {ImageInstance} ADD COLUMN {ProjectID} INT NULL")
    op.execute(
        f"UPDATE {ImageInstance} i "
        f"JOIN {Series} se ON se.{SeriesID} = i.{SeriesID} "
        f"JOIN {Study} sy ON sy.{StudyID} = se.{StudyID} "
        f"JOIN {Patient} p ON p.{PatientID} = sy.{PatientID} "
        f"SET i.{ProjectID} = p.{ProjectID}"
    )
    # Fails, or writes 0, if any row did not get a project. Assumes a strict
    # SQL mode and that every image reaches a patient.
    op.execute(f"ALTER TABLE {ImageInstance} MODIFY {ProjectID} INT NOT NULL")


def downgrade() -> None:
    op.execute(f"ALTER TABLE {ImageInstance} DROP COLUMN {ProjectID}")
