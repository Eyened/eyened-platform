"""add_wf_uwf_to_etdrsfield

Revision ID: 18200354d862
Revises: 2db0e63195db
Create Date: 2026-09-18 11:22:39.382686

Autogenerate does not emit this. Alembic's MySQL type compare
(`DefaultImpl._column_args_match`) only flags a difference between two ENUM
member lists when they have the same length, so appending values is a no-op
to `alembic revision --autogenerate`. Hand-authored to match
ImageInstance.ETDRSField / OptionalEnum(ETDRSField).

Raw SQL with an explicit ALGORITHM/LOCK clause, like its 2026_08_20 siblings,
rather than op.alter_column: left to MySQL's own choice (ALGORITHM=DEFAULT),
appending enum values at the end is INSTANT on this column (1-byte storage,
count stays under 256), but that is exactly the kind of default behaviour
those siblings deliberately do not rely on silently.

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '18200354d862'
down_revision: Union[str, None] = '2db0e63195db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_ENUM = "'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7'"
_NEW_ENUM = "'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'WF', 'UWF'"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE ImageInstance MODIFY ETDRSField ENUM({_NEW_ENUM}) NULL, "
        "ALGORITHM=INSTANT"
    )


def downgrade() -> None:
    # Shrinking the member list is a table rebuild, not INSTANT/INPLACE, and
    # fails outright if any row already stores WF or UWF.
    op.execute(
        f"ALTER TABLE ImageInstance MODIFY ETDRSField ENUM({_OLD_ENUM}) NULL, "
        "ALGORITHM=COPY, LOCK=SHARED"
    )
