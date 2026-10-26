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


def upgrade() -> None:
    op.execute("SET SESSION foreign_key_checks = 1")
    op.execute(
        "SET SESSION sql_mode = "
        "CONCAT_WS(',', NULLIF(@@SESSION.sql_mode, ''), 'STRICT_ALL_TABLES')"
    )
    op.execute("""
        CREATE TABLE TaskProject (
            TaskID INT NOT NULL,
            ProjectID INT NOT NULL,
            DateInserted DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (TaskID, ProjectID),
            CONSTRAINT fk_TaskProject_Task FOREIGN KEY (TaskID)
                REFERENCES Task (TaskID) ON DELETE CASCADE,
            CONSTRAINT fk_TaskProject_Project FOREIGN KEY (ProjectID)
                REFERENCES Project (ProjectID) ON DELETE RESTRICT
        )
    """)
    op.execute("CREATE INDEX ix_TaskProject_Project ON TaskProject (ProjectID)")
    # Later, fk_SubTaskImageLink_TaskProject refuses a link with no matching row here.
    op.execute("""
        INSERT INTO TaskProject (TaskID, ProjectID)
        SELECT DISTINCT st.TaskID, p.ProjectID
        FROM SubTask st
        JOIN SubTaskImageLink sil ON sil.SubTaskID = st.SubTaskID
        JOIN ImageInstance ii ON ii.ImageInstanceID = sil.ImageInstanceID
        JOIN Series se ON se.SeriesID = ii.SeriesID
        JOIN Study sy ON sy.StudyID = se.StudyID
        JOIN Patient p ON p.PatientID = sy.PatientID
    """)


def downgrade() -> None:
    op.execute("DROP TABLE TaskProject")
