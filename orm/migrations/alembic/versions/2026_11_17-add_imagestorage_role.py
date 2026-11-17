"""add ImageStorage.Role

Revision ID: 4b9a6f996bdc
Revises: 18200354d862
Create Date: 2026-11-17 16:06:00.000000

Channel of a file on an ImageInstance, such as angio_flow. The column is
appended so ADD COLUMN can use ALGORITHM=INSTANT (MySQL 8.0.12+ only allows
that when the new column is last).

Guarded so a replay is a no-op. schema-sync stamps a database that is already
at head back to an older revision and runs upgrade head again
(test_upgrade_reconciles_legacy_annotationdata_datemodified).

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision: str = "4b9a6f996bdc"
down_revision: Union[str, None] = "18200354d862"
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


def _index_exists(conn: Connection, table: str, index: str) -> bool:
    """Make CREATE INDEX re-runnable. MySQL has no CREATE INDEX IF NOT EXISTS."""
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = :t AND INDEX_NAME = :i"
            ),
            {"t": table, "i": index},
        ).scalar()
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not _column_exists(conn, "ImageStorage", "Role"):
        op.execute(
            "ALTER TABLE ImageStorage "
            "ADD COLUMN Role VARCHAR(32) NULL, "
            "ALGORITHM=INSTANT"
        )
    if not _index_exists(conn, "ImageStorage", "ix_ImageStorage_ImageInstanceID_Role"):
        op.execute(
            "ALTER TABLE ImageStorage "
            "ADD INDEX ix_ImageStorage_ImageInstanceID_Role (ImageInstanceID, Role), "
            "ALGORITHM=INPLACE, LOCK=NONE"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _index_exists(conn, "ImageStorage", "ix_ImageStorage_ImageInstanceID_Role"):
        op.execute(
            "ALTER TABLE ImageStorage "
            "DROP INDEX ix_ImageStorage_ImageInstanceID_Role, "
            "ALGORITHM=INPLACE, LOCK=NONE"
        )
    if _column_exists(conn, "ImageStorage", "Role"):
        op.execute(
            "ALTER TABLE ImageStorage DROP COLUMN Role, "
            "ALGORITHM=INPLACE, LOCK=NONE"
        )
