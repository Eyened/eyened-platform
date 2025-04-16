"""new ThumbnailPath column

Revision ID: e2fb79ea7982
Revises: c8c36b301f76
Create Date: 2025-03-27 09:32:58.174367

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2fb79ea7982'
down_revision = 'c8c36b301f76'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ImageInstance', sa.Column('ThumbnailPath', sa.String(length=256), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ImageInstance', 'ThumbnailPath')
    # ### end Alembic commands ###
