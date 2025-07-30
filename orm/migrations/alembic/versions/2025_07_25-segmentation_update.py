"""segmentation-update

Revision ID: 9b7fb6c7ead4
Revises: 832ed384515f
Create Date: 2025-07-25 18:29:58.899555

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '9b7fb6c7ead4'
down_revision: Union[str, None] = '832ed384515f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CompositeFeature table: new table for feature hierarchy
    op.create_table('CompositeFeature',
        sa.Column('ParentFeatureID', sa.Integer(), nullable=False),
        sa.Column('ChildFeatureID', sa.Integer(), nullable=False),
        sa.Column('FeatureIndex', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['ChildFeatureID'], ['Feature.FeatureID'], ),
        sa.ForeignKeyConstraint(['ParentFeatureID'], ['Feature.FeatureID'], ),
        sa.PrimaryKeyConstraint('ParentFeatureID', 'ChildFeatureID', 'FeatureIndex')
    )
    op.create_index('fk_CompositeFeature_ChildFeature1_idx', 'CompositeFeature', ['ChildFeatureID'], unique=False)
    op.create_index('fk_CompositeFeature_ParentFeature1_idx', 'CompositeFeature', ['ParentFeatureID'], unique=False)

    # Model table: new table for model metadata
    op.create_table('Model',
        sa.Column('ModelName', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('Version', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('ModelType', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('Description', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('FeatureID', sa.Integer(), nullable=False),
        sa.Column('ModelID', sa.Integer(), nullable=False),
        sa.Column('DateInserted', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['FeatureID'], ['Feature.FeatureID'], ),
        sa.PrimaryKeyConstraint('ModelID'),
        sa.UniqueConstraint('ModelName'),
        sa.UniqueConstraint('ModelName', 'Version'),
        sa.UniqueConstraint('Version')
    )

    # Segmentation table: new table for segmentation data
    op.create_table('Segmentation',
        sa.Column('ZarrArrayIndex', sa.Integer(), nullable=True),
        sa.Column('ImageInstanceID', sa.Integer(), nullable=True),
        sa.Column('Depth', sa.Integer(), nullable=False),
        sa.Column('Height', sa.Integer(), nullable=False),
        sa.Column('Width', sa.Integer(), nullable=False),
        sa.Column('SparseAxis', sa.Integer(), nullable=True),
        sa.Column('ImageProjectionMatrix', sa.JSON(), nullable=True),
        sa.Column('ScanIndices', sa.JSON(), nullable=True),
        sa.Column('DataRepresentation', sa.Enum('Binary', 'DualBitMask', 'Probability', 'MultiLabel', 'MultiClass', name='datarepresentation'), nullable=False),
        sa.Column('DataType', sa.Enum('R8', 'R8UI', 'R16UI', 'R32UI', 'R32F', name='datatype'), nullable=False),
        sa.Column('Threshold', sa.Float(), nullable=False),
        sa.Column('ReferenceSegmentationID', sa.Integer(), nullable=True),
        sa.Column('SegmentationID', sa.Integer(), nullable=False),
        sa.Column('CreatorID', sa.Integer(), nullable=False),
        sa.Column('FeatureID', sa.Integer(), nullable=False),
        sa.Column('SubTaskID', sa.Integer(), nullable=True),
        sa.Column('DateInserted', sa.DateTime(), nullable=False),
        sa.Column('DateModified', sa.DateTime(), nullable=True),
        sa.Column('Inactive', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['CreatorID'], ['Creator.CreatorID'], ),
        sa.ForeignKeyConstraint(['FeatureID'], ['Feature.FeatureID'], ),
        sa.ForeignKeyConstraint(['ImageInstanceID'], ['ImageInstance.ImageInstanceID'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ReferenceSegmentationID'], ['Segmentation.SegmentationID'], ),
        sa.ForeignKeyConstraint(['SubTaskID'], ['SubTask.SubTaskID'], ),
        sa.PrimaryKeyConstraint('SegmentationID')
    )

    # SegmentationModel table: new table for model-generated segmentations
    op.create_table('SegmentationModel',
        sa.Column('ZarrArrayIndex', sa.Integer(), nullable=True),
        sa.Column('ImageInstanceID', sa.Integer(), nullable=True),
        sa.Column('Depth', sa.Integer(), nullable=False),
        sa.Column('Height', sa.Integer(), nullable=False),
        sa.Column('Width', sa.Integer(), nullable=False),
        sa.Column('SparseAxis', sa.Integer(), nullable=True),
        sa.Column('ImageProjectionMatrix', sa.JSON(), nullable=True),
        sa.Column('ScanIndices', sa.JSON(), nullable=True),
        sa.Column('DataRepresentation', sa.Enum('Binary', 'DualBitMask', 'Probability', 'MultiLabel', 'MultiClass', name='datarepresentation'), nullable=False),
        sa.Column('DataType', sa.Enum('R8', 'R8UI', 'R16UI', 'R32UI', 'R32F', name='datatype'), nullable=False),
        sa.Column('Threshold', sa.Float(), nullable=False),
        sa.Column('ReferenceSegmentationID', sa.Integer(), nullable=True),
        sa.Column('SegmentationID', sa.Integer(), nullable=False),
        sa.Column('ModelID', sa.Integer(), nullable=False),
        sa.Column('DateInserted', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['ImageInstanceID'], ['ImageInstance.ImageInstanceID'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ModelID'], ['Model.ModelID'], ),
        sa.ForeignKeyConstraint(['ReferenceSegmentationID'], ['Segmentation.SegmentationID'], ),
        sa.PrimaryKeyConstraint('SegmentationID')
    )

    # Annotation: add self-referencing foreign key
    op.create_foreign_key(None, 'Annotation', 'Annotation', ['AnnotationReferenceID'], ['AnnotationID'])

    # Contact: add Orcid, change Name/Email/Institute to AutoString(255)
    op.add_column('Contact', sa.Column('Orcid', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.alter_column('Contact', 'Name',
               existing_type=mysql.VARCHAR(length=256),
               type_=sqlmodel.sql.sqltypes.AutoString(length=255),
               existing_nullable=False)
    op.alter_column('Contact', 'Email',
               existing_type=mysql.VARCHAR(length=256),
               type_=sqlmodel.sql.sqltypes.AutoString(length=255),
               existing_nullable=False)
    op.alter_column('Contact', 'Institute',
               existing_type=mysql.VARCHAR(length=256),
               type_=sqlmodel.sql.sqltypes.AutoString(length=255),
               existing_nullable=True)

    # Creator: rename MSN to EmployeeIdentifier, add PasswordHash
    op.alter_column('Creator', 'MSN', new_column_name='EmployeeIdentifier', existing_type=mysql.CHAR(length=6), type_=sqlmodel.sql.sqltypes.AutoString(length=255), existing_nullable=True)
    op.add_column('Creator', sa.Column('PasswordHash', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))

    # Feature: drop Modality
    op.drop_column('Feature', 'Modality')

    # FormAnnotation: update foreign key to ImageInstance
    op.drop_constraint('fk_FormAnnotation_ImageInstance1', 'FormAnnotation', type_='foreignkey')
    op.create_foreign_key(None, 'FormAnnotation', 'ImageInstance', ['ImageInstanceID'], ['ImageInstanceID'])

    # FormSchema: change SchemaName to AutoString(255)
    op.alter_column('FormSchema', 'SchemaName',
               existing_type=mysql.VARCHAR(length=45),
               type_=sqlmodel.sql.sqltypes.AutoString(length=255),
               nullable=False)

    # ImageInstance: make DeviceInstanceID non-nullable, drop ThumbnailIdentifier
    op.alter_column('ImageInstance', 'DeviceInstanceID',
               existing_type=mysql.INTEGER(),
               nullable=False)
    op.drop_column('ImageInstance', 'ThumbnailIdentifier')

    # Patient: change PatientIdentifier to AutoString(255)
    op.alter_column('Patient', 'PatientIdentifier',
               existing_type=mysql.VARCHAR(length=45),
               type_=sqlmodel.sql.sqltypes.AutoString(length=255),
               nullable=False)

    # Project: add DOI, change ProjectName to AutoString(255)
    op.add_column('Project', sa.Column('DOI', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.alter_column('Project', 'ProjectName',
               existing_type=mysql.VARCHAR(length=45),
               type_=sqlmodel.sql.sqltypes.AutoString(length=255),
               existing_nullable=False)

    # Series: update foreign key to Study
    op.drop_constraint('fk_Series_Study1', 'Series', type_='foreignkey')
    op.create_foreign_key(None, 'Series', 'Study', ['StudyID'], ['StudyID'])

    # Study: add StudyDate index
    op.create_index('StudyDate_idx', 'Study', ['StudyDate'], unique=False)

    # SubTask: add Comments
    op.add_column('SubTask', sa.Column('Comments', sa.Text(), nullable=True))

    # SubTaskImageLink: drop SubTaskImageLinkID
    op.drop_column('SubTaskImageLink', 'SubTaskImageLinkID')

    # TaskDefinition: add TaskConfig
    op.add_column('TaskDefinition', sa.Column('TaskConfig', sa.JSON(), nullable=True))

    # TaskState: add unique constraint to TaskStateName
    op.create_unique_constraint(None, 'TaskState', ['TaskStateName'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'TaskState', type_='unique')
    op.drop_column('TaskDefinition', 'TaskConfig')
    op.add_column('SubTaskImageLink', sa.Column('SubTaskImageLinkID', mysql.INTEGER(), autoincrement=True, nullable=False))
    op.drop_column('SubTask', 'Comments')
    op.drop_index('StudyDate_idx', table_name='Study')
    op.drop_constraint(None, 'Series', type_='foreignkey')
    op.create_foreign_key('fk_Series_Study1', 'Series', 'Study', ['StudyID'], ['StudyID'], ondelete='CASCADE')
    op.alter_column('Project', 'ProjectName',
               existing_type=sqlmodel.sql.sqltypes.AutoString(length=255),
               type_=mysql.VARCHAR(length=45),
               existing_nullable=False)
    op.drop_column('Project', 'DOI')
    op.alter_column('Patient', 'PatientIdentifier',
               existing_type=sqlmodel.sql.sqltypes.AutoString(length=255),
               type_=mysql.VARCHAR(length=45),
               nullable=True)
    op.add_column('ImageInstance', sa.Column('ThumbnailIdentifier', mysql.VARCHAR(length=256), nullable=True))
    op.alter_column('ImageInstance', 'DeviceInstanceID',
               existing_type=mysql.INTEGER(),
               nullable=True)
    op.alter_column('FormSchema', 'SchemaName',
               existing_type=sqlmodel.sql.sqltypes.AutoString(length=255),
               type_=mysql.VARCHAR(length=45),
               nullable=True)
    op.drop_constraint(None, 'FormAnnotation', type_='foreignkey')
    op.create_foreign_key('fk_FormAnnotation_ImageInstance1', 'FormAnnotation', 'ImageInstance', ['ImageInstanceID'], ['ImageInstanceID'], ondelete='CASCADE')
    op.add_column('Feature', sa.Column('Modality', mysql.ENUM('OCT', 'CF'), nullable=True))
    op.alter_column('Creator', 'EmployeeIdentifier', new_column_name='MSN', existing_type=sqlmodel.sql.sqltypes.AutoString(length=255), type_=mysql.CHAR(length=6), existing_nullable=True)
    op.drop_column('Creator', 'PasswordHash')
    op.alter_column('Contact', 'Institute',
               existing_type=sqlmodel.sql.sqltypes.AutoString(length=255),
               type_=mysql.VARCHAR(length=256),
               existing_nullable=True)
    op.alter_column('Contact', 'Email',
               existing_type=sqlmodel.sql.sqltypes.AutoString(length=255),
               type_=mysql.VARCHAR(length=256),
               existing_nullable=False)
    op.alter_column('Contact', 'Name',
               existing_type=sqlmodel.sql.sqltypes.AutoString(length=255),
               type_=mysql.VARCHAR(length=256),
               existing_nullable=False)
    op.drop_column('Contact', 'Orcid')
    op.drop_constraint(None, 'Annotation', type_='foreignkey')
    op.drop_table('SegmentationModel')
    op.drop_table('Segmentation')
    op.drop_table('Model')
    op.drop_index('fk_CompositeFeature_ParentFeature1_idx', table_name='CompositeFeature')
    op.drop_index('fk_CompositeFeature_ChildFeature1_idx', table_name='CompositeFeature')
    op.drop_table('CompositeFeature')
    # ### end Alembic commands ###
