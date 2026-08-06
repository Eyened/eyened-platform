"""RBAC: ProjectMember table and the two Creator authorization flags.

Revision ID: b2e2800000b2
Revises: c3f5a2b81d94
Create Date: 2026-08-06

Cutover step 1: deploying this alone is invisible to users. The rows are inert
until the enforcing server reads them.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2e2800000b2"
down_revision: Union[str, None] = "c3f5a2b81d94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ProjectMember",
        sa.Column("CreatorID", sa.Integer(), nullable=False),
        sa.Column("ProjectID", sa.Integer(), nullable=False),
        sa.Column(
            "Role",
            sa.Enum("read_only", "grader", "project_admin", name="projectrole"),
            nullable=False,
        ),
        sa.Column(
            "DateInserted",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["CreatorID"], ["Creator.CreatorID"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ProjectID"], ["Project.ProjectID"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("CreatorID", "ProjectID"),
    )
    op.add_column(
        "Creator",
        sa.Column("IsAdmin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "Creator",
        sa.Column("Inactive", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("Creator", "Inactive")
    op.drop_column("Creator", "IsAdmin")
    op.drop_table("ProjectMember")
