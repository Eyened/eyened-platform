"""add AuditLog table

Revision ID: a1d1700000a1
Revises: 624c5700c50f
Create Date: 2026-07-24

Append-only audit sink written in-transaction with the data it records.
ActorID is a plain nullable int, not a FK: audit rows must outlive the
Creator they name.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1d1700000a1"
down_revision: Union[str, None] = "624c5700c50f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "AuditLog",
        sa.Column("AuditLogID", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("Timestamp", sa.DateTime(), nullable=False),
        sa.Column("ActorID", sa.Integer(), nullable=True),
        sa.Column("TrustedPath", sa.String(length=255), nullable=True),
        sa.Column("Action", sa.String(length=16), nullable=False),
        sa.Column("Entity", sa.String(length=64), nullable=False),
        sa.Column("EntityID", sa.String(length=255), nullable=True),
        sa.Column("ProjectID", sa.Integer(), nullable=True),
        sa.Column("Changes", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("AuditLogID"),
    )
    op.create_index("ix_AuditLog_ActorID", "AuditLog", ["ActorID"])
    op.create_index("ix_AuditLog_Timestamp", "AuditLog", ["Timestamp"])


def downgrade() -> None:
    op.drop_index("ix_AuditLog_Timestamp", table_name="AuditLog")
    op.drop_index("ix_AuditLog_ActorID", table_name="AuditLog")
    op.drop_table("AuditLog")
