"""add ImageInstance.ProjectID

Revision ID: d3ce100ab2b6
Revises: b2e2800000b2
Create Date: 2026-08-18 16:08:35.053634

Denormalizes Patient.ProjectID onto ImageInstance so that authorization
scoping is an indexed lookup rather than a five-hop join. The column lands
nullable, is backfilled in committed chunks, and is only then tightened to
NOT NULL -- adding it NOT NULL outright fails on a table with rows.

No index is created here: ProjectID is indexed as the trailing column of the
composite keys added with the composite foreign key, not on its own.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


# revision identifiers, used by Alembic.
revision: str = 'd3ce100ab2b6'
down_revision: Union[str, None] = 'b2e2800000b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    """Make ADD COLUMN re-runnable. MySQL has no ADD COLUMN IF NOT EXISTS."""
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = :t AND COLUMN_NAME = :c"
            ),
            {"t": table, "c": column},
        ).scalar()
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not _column_exists(conn, "ImageInstance", "ProjectID"):
        op.execute(
            "ALTER TABLE ImageInstance ADD COLUMN ProjectID INT NULL, "
            "ALGORITHM=INPLACE, LOCK=NONE"
        )
    # Chunked and committed per chunk: the backfill is a plain UPDATE, so it
    # gets none of the online behaviour above and would otherwise hold row
    # locks on 1.85M rows for ~46s in a single transaction. Without the commit
    # the chunking buys nothing -- the locks accumulate either way.
    lo = conn.execute(sa.text("SELECT MIN(ImageInstanceID) FROM ImageInstance")).scalar()
    hi = conn.execute(sa.text("SELECT MAX(ImageInstanceID) FROM ImageInstance")).scalar()
    step = 20_000
    while lo is not None and lo <= hi:
        conn.execute(
            sa.text("""
                UPDATE ImageInstance i
                  JOIN Series se ON se.SeriesID = i.SeriesID
                  JOIN Study sy ON sy.StudyID = se.StudyID
                  JOIN Patient p ON p.PatientID = sy.PatientID
                SET i.ProjectID = p.ProjectID
                WHERE i.ImageInstanceID BETWEEN :lo AND :hi
            """),
            {"lo": lo, "hi": lo + step - 1},
        )
        conn.commit()
        lo += step
    # The ranged loop read MIN/MAX once, and the ADD COLUMN above ran
    # LOCK=NONE -- so rows inserted concurrently, by code that does not yet
    # have the listener, land above `hi` and the loop never sees them. One
    # unbounded sweep closes that window; it is cheap because the bulk is done.
    conn.execute(
        sa.text("""
            UPDATE ImageInstance i
              JOIN Series se ON se.SeriesID = i.SeriesID
              JOIN Study sy ON sy.StudyID = se.StudyID
              JOIN Patient p ON p.PatientID = sy.PatientID
            SET i.ProjectID = p.ProjectID
            WHERE i.ProjectID IS NULL
        """)
    )
    conn.commit()
    op.execute(
        "ALTER TABLE ImageInstance MODIFY ProjectID INT NOT NULL, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE ImageInstance DROP COLUMN ProjectID, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )
