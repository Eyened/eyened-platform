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


def upgrade() -> None:
    op.execute("SET SESSION foreign_key_checks = 1")
    op.execute(
        "SET SESSION sql_mode = "
        "CONCAT_WS(',', NULLIF(@@SESSION.sql_mode, ''), 'STRICT_ALL_TABLES')"
    )
    op.execute("ALTER TABLE ImageInstance ADD COLUMN ProjectID INT NULL")
    op.execute("""
        UPDATE ImageInstance i
        JOIN Series se ON se.SeriesID = i.SeriesID
        JOIN Study sy ON sy.StudyID = se.StudyID
        JOIN Patient p ON p.PatientID = sy.PatientID
        SET i.ProjectID = p.ProjectID
    """)
    # Fails if any image did not reach a patient.
    op.execute("ALTER TABLE ImageInstance MODIFY ProjectID INT NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE ImageInstance DROP COLUMN ProjectID")
