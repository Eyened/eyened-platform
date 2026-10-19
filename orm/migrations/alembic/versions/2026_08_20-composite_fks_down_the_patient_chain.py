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


# PascalCase. For a lowercase database, comment these and uncomment the next line.
Patient = "Patient"
# Patient = "patient"
Study = "Study"
# Study = "study"
Series = "Series"
# Series = "series"
ImageInstance = "ImageInstance"
# ImageInstance = "imageinstance"
PatientID = "PatientID"
# PatientID = "patientid"
StudyID = "StudyID"
# StudyID = "studyid"
SeriesID = "SeriesID"
# SeriesID = "seriesid"
ImageInstanceID = "ImageInstanceID"
# ImageInstanceID = "imageinstanceid"
ProjectID = "ProjectID"
# ProjectID = "projectid"
FK_STUDY_PATIENT = "Study_ibfk_1"
# FK_STUDY_PATIENT = "study_ibfk_1"
FK_SERIES_STUDY = "Series_ibfk_1"
# FK_SERIES_STUDY = "series_ibfk_1"
FK_IMAGE_SERIES = "fk_ImageInstance_Series1"
# FK_IMAGE_SERIES = "fk_imageinstance_series1"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {Patient} ADD UNIQUE INDEX uq_Patient_Patient_Project "
        f"({PatientID}, {ProjectID})"
    )
    # Error 1091 on a DROP: that constant is not the stored name. A database
    # built from orm_baseline names the image key ImageInstance_ibfk_4.
    # The ADD CONSTRAINT fails if a child's ProjectID does not equal its parent's.
    op.execute(
        f"ALTER TABLE {Study} "
        f"ADD UNIQUE INDEX uq_Study_Study_Project ({StudyID}, {ProjectID}), "
        f"ADD INDEX ix_Study_Patient_Project ({PatientID}, {ProjectID}), "
        f"ADD CONSTRAINT fk_Study_Patient_Project "
        f"FOREIGN KEY ({PatientID}, {ProjectID}) "
        f"REFERENCES {Patient} ({PatientID}, {ProjectID}) "
        f"ON UPDATE CASCADE ON DELETE CASCADE, "
        f"DROP FOREIGN KEY `{FK_STUDY_PATIENT}`"
    )
    op.execute(
        f"ALTER TABLE {Series} "
        f"ADD UNIQUE INDEX uq_Series_Series_Project ({SeriesID}, {ProjectID}), "
        f"ADD INDEX ix_Series_Study_Project ({StudyID}, {ProjectID}), "
        f"ADD CONSTRAINT fk_Series_Study_Project "
        f"FOREIGN KEY ({StudyID}, {ProjectID}) "
        f"REFERENCES {Study} ({StudyID}, {ProjectID}) "
        f"ON UPDATE CASCADE ON DELETE CASCADE, "
        f"DROP FOREIGN KEY `{FK_SERIES_STUDY}`"
    )
    op.execute(
        f"ALTER TABLE {ImageInstance} "
        f"ADD UNIQUE INDEX uq_ImageInstance_Image_Project ({ImageInstanceID}, {ProjectID}), "
        f"ADD INDEX ix_ImageInstance_Series_Project ({SeriesID}, {ProjectID}), "
        f"ADD CONSTRAINT fk_ImageInstance_Series_Project "
        f"FOREIGN KEY ({SeriesID}, {ProjectID}) "
        f"REFERENCES {Series} ({SeriesID}, {ProjectID}) "
        f"ON UPDATE CASCADE ON DELETE CASCADE, "
        f"DROP FOREIGN KEY `{FK_IMAGE_SERIES}`"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {ImageInstance} "
        f"ADD CONSTRAINT fk_ImageInstance_Series_single "
        f"FOREIGN KEY ({SeriesID}) REFERENCES {Series} ({SeriesID}) ON DELETE CASCADE, "
        f"DROP FOREIGN KEY fk_ImageInstance_Series_Project, "
        f"DROP INDEX uq_ImageInstance_Image_Project, "
        f"DROP INDEX ix_ImageInstance_Series_Project"
    )
    op.execute(
        f"ALTER TABLE {Series} "
        f"ADD CONSTRAINT fk_Series_Study_single "
        f"FOREIGN KEY ({StudyID}) REFERENCES {Study} ({StudyID}) ON DELETE CASCADE, "
        f"DROP FOREIGN KEY fk_Series_Study_Project, "
        f"DROP INDEX uq_Series_Series_Project, "
        f"DROP INDEX ix_Series_Study_Project"
    )
    op.execute(
        f"ALTER TABLE {Study} "
        f"ADD CONSTRAINT fk_Study_Patient_single "
        f"FOREIGN KEY ({PatientID}) REFERENCES {Patient} ({PatientID}) ON DELETE CASCADE, "
        f"DROP FOREIGN KEY fk_Study_Patient_Project, "
        f"DROP INDEX uq_Study_Study_Project, "
        f"DROP INDEX ix_Study_Patient_Project"
    )
    op.execute(
        f"ALTER TABLE {Patient} DROP INDEX uq_Patient_Patient_Project"
    )
