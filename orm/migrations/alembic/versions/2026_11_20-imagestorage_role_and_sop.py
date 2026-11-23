"""add ImageStorage.Role and move SOPInstanceUid onto ImageStorage

Revision ID: c7e1a4b90d22
Revises: 18200354d862
Create Date: 2026-11-20 10:00:00.000000

Role names a channel of a file (angio_flow). SOPInstanceUid moves off
ImageInstance so each file can carry its own DICOM instance UID.

The UID is copied onto one primary storage per instance: the lowest
ImageStorageID. IsPrimary is not unique in the database, so copying onto
every primary would put the same UID on two rows and the unique index
would fail after MySQL had already dropped the source column.

Before deploying, count both of these. Neither stops the upgrade.

    SELECT COUNT(*) FROM (
        SELECT ImageInstanceID
        FROM ImageStorage
        WHERE IsPrimary = 1
        GROUP BY ImageInstanceID
        HAVING COUNT(*) > 1
    ) AS multi_primary;

    SELECT COUNT(*)
    FROM ImageInstance AS i
    WHERE i.SOPInstanceUid IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM ImageStorage AS s
          WHERE s.ImageInstanceID = i.ImageInstanceID
            AND s.IsPrimary = 1
      );

An instance with more than one primary keeps the UID on one file. An
instance with a UID and no primary storage loses that UID when the old
column is dropped.

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
    # Derived table: MySQL error 1093 if the UPDATE reads ImageStorage directly.
    # One row per instance, so the unique index below cannot see a duplicated UID.
    op.execute(
        sa.text(
            "UPDATE ImageStorage AS s "
            "JOIN ("
            "    SELECT MIN(ImageStorageID) AS ImageStorageID "
            "    FROM ImageStorage "
            "    WHERE IsPrimary = 1 "
            "    GROUP BY ImageInstanceID"
            ") AS chosen ON chosen.ImageStorageID = s.ImageStorageID "
            "JOIN ImageInstance AS i ON i.ImageInstanceID = s.ImageInstanceID "
            "SET s.SOPInstanceUid = i.SOPInstanceUid "
            "WHERE i.SOPInstanceUid IS NOT NULL"
        )
    )
    # Index first. A duplicate UID then leaves ImageInstance.SOPInstanceUid in place.
    # MySQL commits each DDL statement, so dropping the source column first would
    # make the next upgrade fail on the Role column with the UID already gone.
    op.create_index(
        "uq_ImageStorage_SOPInstanceUid",
        "ImageStorage",
        ["SOPInstanceUid"],
        unique=True,
    )
    op.drop_index("SOPInstanceUid_UNIQUE", table_name="ImageInstance")
    op.drop_column("ImageInstance", "SOPInstanceUid")


def downgrade() -> None:
    op.add_column(
        "ImageInstance",
        sa.Column("SOPInstanceUid", sa.String(length=64), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE ImageInstance AS i "
            "JOIN ImageStorage AS s ON s.ImageInstanceID = i.ImageInstanceID "
            "JOIN ("
            "    SELECT MIN(ImageStorageID) AS ImageStorageID "
            "    FROM ImageStorage "
            "    WHERE IsPrimary = 1 AND SOPInstanceUid IS NOT NULL "
            "    GROUP BY ImageInstanceID"
            ") AS chosen ON chosen.ImageStorageID = s.ImageStorageID "
            "SET i.SOPInstanceUid = s.SOPInstanceUid"
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
