"""update image storage

Revision ID: 533b4abe81b9
Revises: e4247389063f
Create Date: 2026-02-05 16:36:10.858485

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from eyened_orm.image_instance import _make_public_id

# revision identifiers, used by Alembic.
revision: str = '533b4abe81b9'
down_revision: Union[str, None] = 'e4247389063f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Schema Changes ---
    storage_backend_table = op.create_table('StorageBackend',
        sa.Column('StorageBackendID', sa.Integer(), nullable=False),
        sa.Column('Key', sa.String(length=256), nullable=False),
        sa.Column('Kind', sa.String(length=256), nullable=False),
        sa.Column('Config', mysql.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('StorageBackendID')
    )

    storage_info_table = op.create_table('StorageInfo',
        sa.Column('StorageInfoID', sa.Integer(), nullable=False),
        sa.Column('StorageBackendID', sa.Integer(), nullable=False),
        sa.Column('ObjectName', sa.String(length=64), nullable=True),
        sa.Column('ObjectPrefix', sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(['StorageBackendID'], ['StorageBackend.StorageBackendID']),
        sa.PrimaryKeyConstraint('StorageInfoID'),
        sa.UniqueConstraint('StorageBackendID', 'ObjectPrefix')
    )

    op.add_column('ImageInstance', sa.Column('PublicID', sa.String(length=12), nullable=True))
    op.add_column('ImageInstance', sa.Column('StorageInfoID', sa.Integer(), nullable=True))
    op.add_column('ImageInstance', sa.Column('ObjectKey', sa.String(length=256), nullable=False))

    # --- Data Migration (run only in online mode) ---
    connection = op.get_bind()
    if hasattr(connection, 'begin'):
        # Create a default backend
        op.bulk_insert(storage_backend_table,
            [
                {'StorageBackendID': 1, 'Key': 'default', 'Kind': 'local', 'Config': '{}'}
            ]
        )
        
        # Create a default storage info with a null prefix, linked to the default backend
        op.bulk_insert(storage_info_table,
            [
                {'StorageInfoID': 1, 'StorageBackendID': 1, 'ObjectPrefix': None}
            ]
        )
        
        # Update all existing images to use the default storage info
        connection.execute(
            sa.text("UPDATE ImageInstance SET StorageInfoID = 1")
        )

        image_instance_table = sa.Table(
            'ImageInstance',
            sa.MetaData(),
            sa.Column('ImageInstanceID', sa.Integer()),
            sa.Column('PublicID', sa.String(length=12)),
        )

        total_needed = connection.execute(
            sa.select(sa.func.count(image_instance_table.c.ImageInstanceID))
        ).scalar_one()

        if total_needed > 0:
            public_ids: set[str] = set()
            while len(public_ids) < total_needed:
                public_ids.add(_make_public_id())
            public_id_iter = iter(public_ids)

            result = connection.execute(sa.select(image_instance_table.c.ImageInstanceID))
            update_stmt = image_instance_table.update().where(
                image_instance_table.c.ImageInstanceID == sa.bindparam("b_ImageInstanceID")
            ).values(PublicID=sa.bindparam("public_id_val"))
            
            batch_size = 1000
            while True:
                rows = result.fetchmany(batch_size)
                if not rows:
                    break
                params = [
                    {
                        "b_ImageInstanceID": image_id,
                        "public_id_val": next(public_id_iter),
                    }
                    for (image_id,) in rows
                ]
                connection.execute(update_stmt, params)
    else:
        op.execute("-- NOTE: Data migration for StorageInfo and PublicIDs must be run manually or in online mode.")

    # --- Final Schema Changes ---
    op.alter_column('ImageInstance', 'PublicID',
               existing_type=mysql.VARCHAR(length=12),
               nullable=False)
    op.alter_column('ImageInstance', 'StorageInfoID',
               existing_type=mysql.INTEGER(),
               nullable=False)
    op.create_unique_constraint('uq_ImageInstance_PublicID', 'ImageInstance', ['PublicID'])
    op.create_index('ix_ImageInstance_PublicID', 'ImageInstance', ['PublicID'], unique=True)
    op.create_foreign_key('fk_ImageInstance_StorageInfo', 'ImageInstance', 'StorageInfo', ['StorageInfoID'], ['StorageInfoID'])


def downgrade() -> None:
    op.drop_constraint('fk_ImageInstance_StorageInfo', 'ImageInstance', type_='foreignkey')
    op.drop_index('ix_ImageInstance_PublicID', table_name='ImageInstance')
    op.drop_constraint('uq_ImageInstance_PublicID', 'ImageInstance', type_='unique')
    op.drop_column('ImageInstance', 'ObjectKey')
    op.drop_column('ImageInstance', 'StorageInfoID')
    op.drop_column('ImageInstance', 'PublicID')
    op.drop_table('StorageInfo')
    op.drop_table('StorageBackend')
