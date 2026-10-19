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


# PascalCase. Comment this block and uncomment the lowercase block below.
ImageInstance = "ImageInstance"
Series = "Series"
Study = "Study"
Patient = "Patient"
ProjectID = "ProjectID"
ImageInstanceID = "ImageInstanceID"
SeriesID = "SeriesID"
StudyID = "StudyID"
PatientID = "PatientID"

# ImageInstance = "imageinstance"
# Series = "series"
# Study = "study"
# Patient = "patient"
# ProjectID = "projectid"
# ImageInstanceID = "imageinstanceid"
# SeriesID = "seriesid"
# StudyID = "studyid"
# PatientID = "patientid"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {ImageInstance} ADD COLUMN {ProjectID} INT NULL")
    op.execute(f"""
        UPDATE {ImageInstance} i
        JOIN {Series} se ON se.{SeriesID} = i.{SeriesID}
        JOIN {Study} sy ON sy.{StudyID} = se.{StudyID}
        JOIN {Patient} p ON p.{PatientID} = sy.{PatientID}
        SET i.{ProjectID} = p.{ProjectID}
    """)
    # Fails, or writes 0, if any row did not get a project. Assumes a strict
    # SQL mode and that every image reaches a patient.
    op.execute(f"ALTER TABLE {ImageInstance} MODIFY {ProjectID} INT NOT NULL")


def downgrade() -> None:
    op.execute(f"ALTER TABLE {ImageInstance} DROP COLUMN {ProjectID}")
