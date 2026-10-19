"""Add WF and UWF to ImageInstance.ETDRSField.

Revision ID: 18200354d862
Revises: 5f1c2a9d7e30
"""
from typing import Sequence, Union

from alembic import op


revision: str = "18200354d862"
down_revision: Union[str, None] = "5f1c2a9d7e30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PascalCase. Comment this block and uncomment the lowercase block below.
ImageInstance = "ImageInstance"
ETDRSField = "ETDRSField"

# ImageInstance = "imageinstance"
# ETDRSField = "etdrsfield"

_OLD_ENUM = "'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7'"
_NEW_ENUM = "'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'WF', 'UWF'"


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE {ImageInstance}
        MODIFY {ETDRSField} ENUM({_NEW_ENUM}) NULL,
        ALGORITHM=INSTANT
    """)


def downgrade() -> None:
    # Fails outright if any row already stores WF or UWF.
    op.execute(f"""
        ALTER TABLE {ImageInstance}
        MODIFY {ETDRSField} ENUM({_OLD_ENUM}) NULL,
        ALGORITHM=COPY, LOCK=SHARED
    """)
