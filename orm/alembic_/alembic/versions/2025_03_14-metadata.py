"""metadata

Revision ID: 781e14a57819
Revises: c04645bec436
Create Date: 2025-03-14 13:42:19.778726

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '781e14a57819'
down_revision = 'c04645bec436'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('Contact',
    sa.Column('ContactID', sa.Integer(), nullable=False),
    sa.Column('Name', sa.String(length=256), nullable=False),
    sa.Column('Email', sa.String(length=256), nullable=False),
    sa.Column('Institute', sa.String(length=256), nullable=True),
    sa.PrimaryKeyConstraint('ContactID', name=op.f('ContactID')),
    sa.UniqueConstraint('Name', 'Email', 'Institute', name='NameEmailInstitute_UNIQUE')
    )
    op.add_column('Project', sa.Column('Description', sa.Text(), nullable=True))
    op.add_column('Project', sa.Column('ContactID', sa.Integer(), nullable=True))
    op.create_foreign_key(op.f('fk_Project_Contact1'), 'Project', 'Contact', ['ContactID'], ['ContactID'])
    op.add_column('Task', sa.Column('Description', sa.Text(), nullable=True))
    op.add_column('Task', sa.Column('ContactID', sa.Integer(), nullable=True))
    op.create_foreign_key(op.f('fk_Task_Contact1'), 'Task', 'Contact', ['ContactID'], ['ContactID'])
    op.add_column('FormAnnotation', sa.Column('FormAnnotationReferenceID', sa.Integer(), nullable=True))
    op.create_foreign_key(op.f('fk_FormAnnotation_FormAnnotation1'), 'FormAnnotation', 'FormAnnotation', ['FormAnnotationReferenceID'], ['FormAnnotationID'])
    op.alter_column('Task', 'TaskStateID',
            existing_type=mysql.INTEGER(),
            nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    op.alter_column('Task', 'TaskStateID',
            existing_type=mysql.INTEGER(),
            nullable=False)
    op.drop_constraint(op.f('fk_FormAnnotation_FormAnnotation1'), 'FormAnnotation', type_='foreignkey')
    op.drop_column('FormAnnotation', 'FormAnnotationReferenceID')
    op.drop_constraint(op.f('fk_Task_Contact1'), 'Task', type_='foreignkey')
    op.drop_column('Task', 'ContactID')
    op.drop_column('Task', 'Description')
    op.drop_constraint(op.f('fk_Project_Contact1'), 'Project', type_='foreignkey')
    op.drop_column('Project', 'ContactID')
    op.drop_column('Project', 'Description')
    op.drop_table('Contact')
    # ### end Alembic commands ###
