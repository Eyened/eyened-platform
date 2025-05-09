"""new image hash and study round columns

Revision ID: 832ed384515f
Revises: e2fb79ea7982
Create Date: 2025-04-03 13:33:35.691067

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '832ed384515f'
down_revision = 'e2fb79ea7982'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ImageInstance', sa.Column('FileChecksum', sa.LargeBinary(length=16), nullable=True))
    op.add_column('ImageInstance', sa.Column('DataHash', sa.LargeBinary(length=32), nullable=True))
    op.create_index(op.f('DatasetIdentifier'), 'ImageInstance', ['DatasetIdentifier'], unique=False)
    op.add_column('Study', sa.Column('StudyRound', sa.Integer(), nullable=True))
    op.create_index(op.f('StudyRound'), 'Study', ['StudyRound'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('StudyRound'), table_name='Study')
    op.drop_column('Study', 'StudyRound')
    op.drop_index(op.f('DatasetIdentifier'), table_name='ImageInstance')
    op.drop_column('ImageInstance', 'DataHash')
    op.drop_column('ImageInstance', 'FileChecksum')
    # ### end Alembic commands ###
