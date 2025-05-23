"""fix inactive data

Revision ID: a7c0a9667796
Revises: fbca4c2617b0
Create Date: 2024-10-08 17:07:26.708343

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a7c0a9667796'
down_revision = 'fbca4c2617b0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    # change Annotation.Inactive to bool
    op.alter_column('Annotation', 'Inactive', existing_type=mysql.ENUM('Y'), new_column_name='Inactive_')
    op.add_column('Annotation', sa.Column('Inactive', sa.Boolean, nullable=False, default=0))
    op.execute("UPDATE Annotation SET Inactive = 1 WHERE Inactive_ = 'Y'")
    op.drop_column('Annotation', 'Inactive_')


    # change FormAnnotation.Inactive to bool
    op.alter_column('FormAnnotation', 'Inactive', existing_type=mysql.ENUM('Y'), new_column_name='Inactive_')
    op.add_column('FormAnnotation', sa.Column('Inactive', sa.Boolean, nullable=False, default=0))
    op.execute("UPDATE FormAnnotation SET Inactive = 1 WHERE Inactive_ = 'Y'")
    op.drop_column('FormAnnotation', 'Inactive_')

    
    # change ImageInstance.InactiveData to ImageInstance.Inactive and make not null
    # change FormAnnotation.Inactive to bool
    op.alter_column('ImageInstance', 'InactiveData', existing_type=mysql.BOOLEAN, new_column_name='Inactive')
    op.execute("UPDATE ImageInstance SET Inactive = 0 WHERE Inactive IS NULL")
    op.alter_column('ImageInstance', 'Inactive', existing_type=mysql.BOOLEAN, nullable=False)

