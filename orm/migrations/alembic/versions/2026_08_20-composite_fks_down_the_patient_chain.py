"""Point Study, Series, and ImageInstance at their parent's ProjectID.

Revision ID: b45090e1544e
Revises: 99724789b34d
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b45090e1544e"
down_revision: Union[str, None] = "99724789b34d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PascalCase. Comment this block and uncomment the lowercase block below.
Patient = "Patient"
Study = "Study"
Series = "Series"
ImageInstance = "ImageInstance"
PatientID = "PatientID"
StudyID = "StudyID"
SeriesID = "SeriesID"
ImageInstanceID = "ImageInstanceID"
ProjectID = "ProjectID"
FK_STUDY_PATIENT = "Study_ibfk_1"
FK_SERIES_STUDY = "Series_ibfk_1"
FK_IMAGE_SERIES = "fk_ImageInstance_Series1"

# Patient = "patient"
# Study = "study"
# Series = "series"
# ImageInstance = "imageinstance"
# PatientID = "patientid"
# StudyID = "studyid"
# SeriesID = "seriesid"
# ImageInstanceID = "imageinstanceid"
# ProjectID = "projectid"
# FK_STUDY_PATIENT = "study_ibfk_1"
# FK_SERIES_STUDY = "series_ibfk_1"
# FK_IMAGE_SERIES = "fk_imageinstance_series1"


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE {Patient}
        ADD UNIQUE INDEX uq_Patient_Patient_Project ({PatientID}, {ProjectID})
    """)
    # Error 1091 on a DROP: that constant is not the stored name. A database
    # built from orm_baseline names the image key ImageInstance_ibfk_4.
    # The ADD CONSTRAINT fails if a child's ProjectID does not equal its parent's.
    op.execute(f"""
        ALTER TABLE {Study}
            ADD UNIQUE INDEX uq_Study_Study_Project ({StudyID}, {ProjectID}),
            ADD INDEX ix_Study_Patient_Project ({PatientID}, {ProjectID}),
            ADD CONSTRAINT fk_Study_Patient_Project
                FOREIGN KEY ({PatientID}, {ProjectID})
                REFERENCES {Patient} ({PatientID}, {ProjectID})
                ON UPDATE CASCADE ON DELETE CASCADE,
            DROP FOREIGN KEY `{FK_STUDY_PATIENT}`
    """)
    op.execute(f"""
        ALTER TABLE {Series}
            ADD UNIQUE INDEX uq_Series_Series_Project ({SeriesID}, {ProjectID}),
            ADD INDEX ix_Series_Study_Project ({StudyID}, {ProjectID}),
            ADD CONSTRAINT fk_Series_Study_Project
                FOREIGN KEY ({StudyID}, {ProjectID})
                REFERENCES {Study} ({StudyID}, {ProjectID})
                ON UPDATE CASCADE ON DELETE CASCADE,
            DROP FOREIGN KEY `{FK_SERIES_STUDY}`
    """)
    op.execute(f"""
        ALTER TABLE {ImageInstance}
            ADD UNIQUE INDEX uq_ImageInstance_Image_Project ({ImageInstanceID}, {ProjectID}),
            ADD INDEX ix_ImageInstance_Series_Project ({SeriesID}, {ProjectID}),
            ADD CONSTRAINT fk_ImageInstance_Series_Project
                FOREIGN KEY ({SeriesID}, {ProjectID})
                REFERENCES {Series} ({SeriesID}, {ProjectID})
                ON UPDATE CASCADE ON DELETE CASCADE,
            DROP FOREIGN KEY `{FK_IMAGE_SERIES}`
    """)


def downgrade() -> None:
    op.execute(f"""
        ALTER TABLE {ImageInstance}
            ADD CONSTRAINT fk_ImageInstance_Series_single
                FOREIGN KEY ({SeriesID}) REFERENCES {Series} ({SeriesID}) ON DELETE CASCADE,
            DROP FOREIGN KEY fk_ImageInstance_Series_Project,
            DROP INDEX uq_ImageInstance_Image_Project,
            DROP INDEX ix_ImageInstance_Series_Project
    """)
    op.execute(f"""
        ALTER TABLE {Series}
            ADD CONSTRAINT fk_Series_Study_single
                FOREIGN KEY ({StudyID}) REFERENCES {Study} ({StudyID}) ON DELETE CASCADE,
            DROP FOREIGN KEY fk_Series_Study_Project,
            DROP INDEX uq_Series_Series_Project,
            DROP INDEX ix_Series_Study_Project
    """)
    op.execute(f"""
        ALTER TABLE {Study}
            ADD CONSTRAINT fk_Study_Patient_single
                FOREIGN KEY ({PatientID}) REFERENCES {Patient} ({PatientID}) ON DELETE CASCADE,
            DROP FOREIGN KEY fk_Study_Patient_Project,
            DROP INDEX uq_Study_Study_Project,
            DROP INDEX ix_Study_Patient_Project
    """)
    op.execute(
        f"ALTER TABLE {Patient} DROP INDEX uq_Patient_Patient_Project"
    )
