"""Give AnnotationData.DateModified its current-timestamp default.

Revision ID: 5f1c2a9d7e30
Revises: 2db0e63195db
"""
from typing import Sequence, Union

from alembic import op


revision: str = "5f1c2a9d7e30"
down_revision: Union[str, None] = "2db0e63195db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PascalCase. For a lowercase database, comment these and uncomment the next line.
AnnotationData = "AnnotationData"
# AnnotationData = "annotationdata"
DateModified = "DateModified"
# DateModified = "datemodified"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {AnnotationData} MODIFY {DateModified} DATETIME NULL "
        f"DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {AnnotationData} MODIFY {DateModified} DATETIME NULL"
    )
