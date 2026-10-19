"""Copy ProjectID onto Study, then onto Series.

Revision ID: 4eae42457fa2
Revises: d3ce100ab2b6
"""
from typing import Sequence, Union

from alembic import op


revision: str = "4eae42457fa2"
down_revision: Union[str, None] = "d3ce100ab2b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PascalCase. Comment this block and uncomment the lowercase block below.
Study = "Study"
Series = "Series"
Patient = "Patient"
ProjectID = "ProjectID"
StudyID = "StudyID"
SeriesID = "SeriesID"
PatientID = "PatientID"

# Study = "study"
# Series = "series"
# Patient = "patient"
# ProjectID = "projectid"
# StudyID = "studyid"
# SeriesID = "seriesid"
# PatientID = "patientid"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {Study} ADD COLUMN {ProjectID} INT NULL")
    op.execute(f"""
        UPDATE {Study} t
        JOIN {Patient} p ON p.{PatientID} = t.{PatientID}
        SET t.{ProjectID} = p.{ProjectID}
    """)
    # Fails, or writes 0, if any row did not get a project. Assumes a strict SQL mode.
    op.execute(f"ALTER TABLE {Study} MODIFY {ProjectID} INT NOT NULL")

    op.execute(f"ALTER TABLE {Series} ADD COLUMN {ProjectID} INT NULL")
    op.execute(f"""
        UPDATE {Series} t
        JOIN {Study} s ON s.{StudyID} = t.{StudyID}
        SET t.{ProjectID} = s.{ProjectID}
    """)
    # Fails, or writes 0, if Study.ProjectID was not filled. Assumes a strict SQL mode.
    op.execute(f"ALTER TABLE {Series} MODIFY {ProjectID} INT NOT NULL")


def downgrade() -> None:
    op.execute(f"ALTER TABLE {Series} DROP COLUMN {ProjectID}")
    op.execute(f"ALTER TABLE {Study} DROP COLUMN {ProjectID}")
