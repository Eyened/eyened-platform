"""add ProjectMember and Creator.Inactive

Revision ID: b7e4c2a10f38
Revises: c3f5a2b81d94
Create Date: 2026-07-30

RBAC Step 2 / P2 schema. Two additive changes:

- ``ProjectMember``: one row = one creator's role in one project. The composite
  PK ``(CreatorID, ProjectID)`` makes "exactly one role per project" structural,
  and its CreatorID-leading order serves the scope resolution that runs on every
  request. ``ondelete`` differs per parent deliberately: deleting a project
  CASCADEs its now-meaningless grants, while deleting a creator RESTRICTs --
  deletion is deactivation, so a creator delete should fail loudly rather than
  silently drop an access-review record.
- ``Creator.Inactive``: the deactivation flag that makes that true.

``Creator.Role`` needs no DDL -- it already exists on every deployment, because
schema is built by ``Base.metadata.create_all`` and the Alembic revisions are
incremental ALTERs on that baseline.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e4c2a10f38"
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
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["CreatorID"], ["Creator.CreatorID"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ProjectID"], ["Project.ProjectID"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("CreatorID", "ProjectID"),
    )
    op.create_index("fk_ProjectMember_Creator1_idx", "ProjectMember", ["CreatorID"])
    op.create_index("fk_ProjectMember_Project1_idx", "ProjectMember", ["ProjectID"])

    # Two statements, not one: the model carries only a Python-side default
    # (matching Annotation/ImageInstance, whose server defaults 2025_10_23-2
    # deliberately set to None), so a lingering server default here would be
    # permanent drift against Base.metadata. Adding it *with* a default
    # first makes the backfill of the existing rows explicit rather than relying
    # on MySQL's implicit default for a NOT NULL column.
    op.add_column(
        "Creator",
        sa.Column(
            "Inactive", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.alter_column(
        "Creator",
        "Inactive",
        existing_type=sa.Boolean(),
        server_default=None,
        existing_nullable=False,
    )


def downgrade() -> None:
    # No explicit drop_index calls here (contrast 2026_07_24-add_audit_log.py,
    # whose downgrade drops its own indexes before its table): DROP TABLE already
    # removes a table's own indexes and constraints. That shape is NOT safe to
    # copy back onto ProjectMember -- fk_ProjectMember_Project1_idx backs the
    # ProjectID FK (its leading column), and InnoDB refuses to drop an index
    # while the FK it backs still exists (errno 1553). AuditLog's downgrade gets
    # away with dropping indexes explicitly only because AuditLog has no FKs.
    # Order matters: drop_column first. MySQL DDL auto-commits per statement and
    # Alembic stamps alembic_version only after this function returns, so a
    # failure between the two (a metadata-lock timeout on the live Creator table
    # is the realistic one) must not have already destroyed the grants. This
    # order also makes downgrade() the exact statement-order inverse of
    # upgrade(), which adds ProjectMember first and Creator.Inactive second.
    op.drop_column("Creator", "Inactive")
    op.drop_table("ProjectMember")
