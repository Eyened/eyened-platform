"""renaming of enums

Revision ID: 7aff6bc32315
Revises: 
Create Date: 2024-07-30 18:13:28.130881

"""
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

# revision identifiers, used by Alembic.
revision = '7aff6bc32315'
branch_labels = None
depends_on = None
down_revision = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    # first we add the new enum values types
    op.alter_column('Feature', 'Modality',
               existing_type=mysql.ENUM('Color Fundus', 'OCT'),
               type_=sa.Enum('Color Fundus', 'OCT', 'CF', name='featuremodalityenum'),
               existing_nullable=True)
    # then we reasign the data
    op.execute("UPDATE Feature SET Modality = 'CF' WHERE Modality = 'Color Fundus'")
    # now we drop the old enum values
    op.alter_column('Feature', 'Modality',
               type_=sa.Enum('OCT', 'CF', name='featuremodalityenum'),
               existing_nullable=True)

    
    ### AnatomicRegionArtificial enum remapping
    # first we add the new enum values types
    op.alter_column('ImageInstance', 'AnatomicRegionArtificial',
               existing_type=mysql.ENUM('1', '2', 'External', '1-Stereo', 'Lens', 'Neitz', 'Other', 'Unknown', 'Ungradable'),
               type_=sa.Enum('1', '2', 'External', '1-Stereo', 'Lens', 'Neitz', 'Other', 'Unknown', 'Ungradable', 'Disc', 'Macula', 'MaculaStereo', name='anatomic_region_artificial_enum'),
               existing_nullable=True)
    
    # then we reasign the data
    op.execute("UPDATE ImageInstance SET AnatomicRegionArtificial = 'Disc' WHERE AnatomicRegionArtificial = '1'")
    op.execute("UPDATE ImageInstance SET AnatomicRegionArtificial = 'Macula' WHERE AnatomicRegionArtificial = '2'")
    op.execute("UPDATE ImageInstance SET AnatomicRegionArtificial = 'MaculaStereo' WHERE AnatomicRegionArtificial = '1-Stereo'")

    # now we drop the old enum values
    op.alter_column('ImageInstance', 'AnatomicRegionArtificial',
               type_=sa.Enum('Disc', 'Macula', 'External', 'MaculaStereo', 'Lens', 'Neitz', 'Other', 'Unknown', 'Ungradable', name='anatomic_region_artificial_enum'),
               existing_nullable=True)
    
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
