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


def upgrade() -> None:
    op.execute("SET SESSION foreign_key_checks = 1")
    op.execute(
        "SET SESSION sql_mode = "
        "CONCAT_WS(',', NULLIF(@@SESSION.sql_mode, ''), 'STRICT_ALL_TABLES')"
    )
    op.execute("ALTER TABLE Study ADD COLUMN ProjectID INT NULL")
    op.execute("""
        UPDATE Study t
        JOIN Patient p ON p.PatientID = t.PatientID
        SET t.ProjectID = p.ProjectID
    """)
    # Fails if any study did not get a project.
    op.execute("ALTER TABLE Study MODIFY ProjectID INT NOT NULL")

    op.execute("ALTER TABLE Series ADD COLUMN ProjectID INT NULL")
    op.execute("""
        UPDATE Series t
        JOIN Study s ON s.StudyID = t.StudyID
        SET t.ProjectID = s.ProjectID
    """)
    # Fails if any series did not get a project.
    op.execute("ALTER TABLE Series MODIFY ProjectID INT NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE Series DROP COLUMN ProjectID")
    op.execute("ALTER TABLE Study DROP COLUMN ProjectID")
