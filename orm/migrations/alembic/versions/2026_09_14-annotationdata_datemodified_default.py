"""annotationdata datemodified default

Revision ID: 5f1c2a9d7e30
Revises: 2db0e63195db
Create Date: 2026-09-14 14:44:10.517043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '5f1c2a9d7e30'
down_revision: Union[str, None] = '2db0e63195db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('AnnotationData', 'DateModified',
               existing_type=mysql.DATETIME(),
               server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
               existing_nullable=True)


def downgrade() -> None:
    op.alter_column('AnnotationData', 'DateModified',
               existing_type=mysql.DATETIME(),
               server_default=None,
               existing_nullable=True)
