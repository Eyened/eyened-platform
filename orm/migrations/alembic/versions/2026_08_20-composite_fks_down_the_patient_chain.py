"""Point Study, Series, and ImageInstance at their parent's ProjectID.

About 9 minutes for a 1.76 GB ImageInstance table (about 0.2 s per MB).

Revision ID: b45090e1544e
Revises: 99724789b34d
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b45090e1544e"
down_revision: Union[str, None] = "99724789b34d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk_name(table: str, column: str, referred_table: str) -> str:
    """Return the name of the one foreign key from table.column to referred_table."""
    names = op.get_bind().execute(
        sa.text(
            "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
            " AND COLUMN_NAME = :column AND REFERENCED_TABLE_NAME = :referred_table"
        ),
        {"table": table, "column": column, "referred_table": referred_table},
    ).scalars().all()
    if len(names) != 1:
        raise RuntimeError(
            f"expected one foreign key {table}.{column} -> {referred_table}, found {names}"
        )
    return names[0]


def upgrade() -> None:
    op.execute("SET SESSION foreign_key_checks = 1")
    op.execute(
        "SET SESSION sql_mode = "
        "CONCAT_WS(',', NULLIF(@@SESSION.sql_mode, ''), 'STRICT_ALL_TABLES')"
    )
    # Look up every name that varies between databases before the first ALTER.
    fk_study_patient = _fk_name("Study", "PatientID", "Patient")
    fk_series_study = _fk_name("Series", "StudyID", "Study")
    fk_image_series = _fk_name("ImageInstance", "SeriesID", "Series")

    op.execute("""
        ALTER TABLE Patient
        ADD UNIQUE INDEX uq_Patient_Patient_Project (PatientID, ProjectID)
    """)
    # The ADD CONSTRAINT fails if a child's ProjectID does not equal its parent's.
    op.execute(f"""
        ALTER TABLE Study
            ADD UNIQUE INDEX uq_Study_Study_Project (StudyID, ProjectID),
            ADD INDEX ix_Study_Patient_Project (PatientID, ProjectID),
            ADD CONSTRAINT fk_Study_Patient_Project
                FOREIGN KEY (PatientID, ProjectID)
                REFERENCES Patient (PatientID, ProjectID)
                ON UPDATE CASCADE ON DELETE CASCADE,
            DROP FOREIGN KEY `{fk_study_patient}`
    """)
    op.execute(f"""
        ALTER TABLE Series
            ADD UNIQUE INDEX uq_Series_Series_Project (SeriesID, ProjectID),
            ADD INDEX ix_Series_Study_Project (StudyID, ProjectID),
            ADD CONSTRAINT fk_Series_Study_Project
                FOREIGN KEY (StudyID, ProjectID)
                REFERENCES Study (StudyID, ProjectID)
                ON UPDATE CASCADE ON DELETE CASCADE,
            DROP FOREIGN KEY `{fk_series_study}`
    """)
    op.execute(f"""
        ALTER TABLE ImageInstance
            ADD UNIQUE INDEX uq_ImageInstance_Image_Project (ImageInstanceID, ProjectID),
            ADD INDEX ix_ImageInstance_Series_Project (SeriesID, ProjectID),
            ADD CONSTRAINT fk_ImageInstance_Series_Project
                FOREIGN KEY (SeriesID, ProjectID)
                REFERENCES Series (SeriesID, ProjectID)
                ON UPDATE CASCADE ON DELETE CASCADE,
            DROP FOREIGN KEY `{fk_image_series}`
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE ImageInstance
            ADD CONSTRAINT fk_ImageInstance_Series_single
                FOREIGN KEY (SeriesID) REFERENCES Series (SeriesID) ON DELETE CASCADE,
            DROP FOREIGN KEY fk_ImageInstance_Series_Project,
            DROP INDEX uq_ImageInstance_Image_Project,
            DROP INDEX ix_ImageInstance_Series_Project
    """)
    op.execute("""
        ALTER TABLE Series
            ADD CONSTRAINT fk_Series_Study_single
                FOREIGN KEY (StudyID) REFERENCES Study (StudyID) ON DELETE CASCADE,
            DROP FOREIGN KEY fk_Series_Study_Project,
            DROP INDEX uq_Series_Series_Project,
            DROP INDEX ix_Series_Study_Project
    """)
    op.execute("""
        ALTER TABLE Study
            ADD CONSTRAINT fk_Study_Patient_single
                FOREIGN KEY (PatientID) REFERENCES Patient (PatientID) ON DELETE CASCADE,
            DROP FOREIGN KEY fk_Study_Patient_Project,
            DROP INDEX uq_Study_Study_Project,
            DROP INDEX ix_Study_Patient_Project
    """)
    op.execute("ALTER TABLE Patient DROP INDEX uq_Patient_Patient_Project")
