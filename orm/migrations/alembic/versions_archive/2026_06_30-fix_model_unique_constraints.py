"""fix model unique constraints

Revision ID: 624c5700c50f
Revises: 7b36f07198ee
Create Date: 2026-06-30 17:28:58.419998

Drop the legacy ModelName-only unique index on Model so multiple versions
of the same model name can coexist. Keep the (ModelName, Version) unique
index (ModelName_Version or ModelName_2 depending on how MySQL named it).

Alembic autogenerate does not detect this drop reliably on MySQL when a
composite unique on the same leading column remains — see sqlalchemy/alembic#276.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '624c5700c50f'
down_revision: Union[str, None] = '7b36f07198ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MySQL implements UNIQUE as an index named after the first constraint.
    op.drop_index('ModelName', table_name='Model')


def downgrade() -> None:
    op.create_index('ModelName', 'Model', ['ModelName'], unique=True)
