"""add ImageStorage.Role and move SOPInstanceUid onto ImageStorage

Revision ID: c7e1a4b90d22
Revises: 18200354d862
Create Date: 2026-11-20 10:00:00.000000

Role names a channel of a file (angio_flow). SOPInstanceUid moves off
ImageInstance so each file can carry its own DICOM instance UID. Existing
values are copied onto the primary storage row.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e1a4b90d22"
down_revision: Union[str, None] = "18200354d862"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ImageStorage",
        sa.Column("Role", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "ImageStorage",
        sa.Column("SOPInstanceUid", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_ImageStorage_ImageInstanceID_Role",
        "ImageStorage",
        ["ImageInstanceID", "Role"],
    )
    op.execute(
        sa.text(
            "UPDATE ImageStorage AS s "
            "JOIN ImageInstance AS i ON i.ImageInstanceID = s.ImageInstanceID "
            "SET s.SOPInstanceUid = i.SOPInstanceUid "
            "WHERE s.IsPrimary = 1 AND i.SOPInstanceUid IS NOT NULL"
        )
    )
    op.drop_index("SOPInstanceUid_UNIQUE", table_name="ImageInstance")
    op.drop_column("ImageInstance", "SOPInstanceUid")
    op.create_index(
        "uq_ImageStorage_SOPInstanceUid",
        "ImageStorage",
        ["SOPInstanceUid"],
        unique=True,
    )


def downgrade() -> None:
    op.add_column(
        "ImageInstance",
        sa.Column("SOPInstanceUid", sa.String(length=64), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE ImageInstance AS i "
            "JOIN ImageStorage AS s ON s.ImageInstanceID = i.ImageInstanceID "
            "SET i.SOPInstanceUid = s.SOPInstanceUid "
            "WHERE s.IsPrimary = 1 AND s.SOPInstanceUid IS NOT NULL"
        )
    )
    op.create_index(
        "SOPInstanceUid_UNIQUE",
        "ImageInstance",
        ["SOPInstanceUid"],
        unique=True,
    )
    op.drop_index("uq_ImageStorage_SOPInstanceUid", table_name="ImageStorage")
    op.drop_index("ix_ImageStorage_ImageInstanceID_Role", table_name="ImageStorage")
    op.drop_column("ImageStorage", "SOPInstanceUid")
    op.drop_column("ImageStorage", "Role")
