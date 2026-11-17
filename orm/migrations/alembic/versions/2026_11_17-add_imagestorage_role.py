"""add ImageStorage.Role

Revision ID: 4b9a6f996bdc
Revises: 18200354d862
Create Date: 2026-11-17 16:06:00.000000

Channel of a file on an ImageInstance, such as angio_flow. The column is
appended so ADD COLUMN can use ALGORITHM=INSTANT (MySQL 8.0.12+ only allows
that when the new column is last).

"""
from typing import Sequence, Union

from alembic import op


revision: str = "4b9a6f996bdc"
down_revision: Union[str, None] = "18200354d862"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ImageStorage "
        "ADD COLUMN Role VARCHAR(32) NULL, "
        "ALGORITHM=INSTANT"
    )
    op.execute(
        "ALTER TABLE ImageStorage "
        "ADD INDEX ix_ImageStorage_ImageInstanceID_Role (ImageInstanceID, Role), "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE ImageStorage "
        "DROP INDEX ix_ImageStorage_ImageInstanceID_Role, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )
    op.execute(
        "ALTER TABLE ImageStorage DROP COLUMN Role, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )
